"""Persistent incident and response state for the CIDRS API."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from src.responder.firewall_provider import FirewallProvider


class ResponseEngine:
    def __init__(self, db_path=None, use_aws=False):
        self.use_aws = use_aws
        self.db_path = Path(db_path or 'data/incidents.db')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = Lock()
        self.firewall = FirewallProvider()
        self.init_database()

    def init_database(self):
        with self.lock, self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source_ip TEXT NOT NULL,
                    is_attack INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    model_votes TEXT NOT NULL DEFAULT '{}'
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS blocked_ips (
                    ip TEXT PRIMARY KEY,
                    blocked_at TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    automatic INTEGER NOT NULL DEFAULT 0
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            ''')
            columns = {row['name'] for row in self.conn.execute('PRAGMA table_info(incidents)').fetchall()}
            if 'model_votes' not in columns:
                self.conn.execute("ALTER TABLE incidents ADD COLUMN model_votes TEXT NOT NULL DEFAULT '{}'")

    def log_incident(self, incident):
        with self.lock, self.conn:
            cursor = self.conn.execute('''
                INSERT INTO incidents
                    (timestamp, source_ip, is_attack, confidence, risk_level, model_votes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                incident.get('timestamp', datetime.now(timezone.utc).isoformat()),
                incident.get('source_ip', 'unknown'),
                1 if incident.get('is_attack') else 0,
                incident.get('confidence', 0),
                incident.get('risk_level', 'LOW'),
                incident.get('model_votes', '{}'),
            ))
            return {'status': 'logged', 'incident_id': cursor.lastrowid}

    def get_recent_incidents(self, limit=50, since=None):
        query = 'SELECT * FROM incidents'
        params = []
        if since:
            query += ' WHERE timestamp >= ?'
            params.append(since)
        query += ' ORDER BY id DESC LIMIT ?'
        params.append(max(1, min(int(limit), 1000)))
        with self.lock:
            rows = self.conn.execute(query, params).fetchall()
        return [self._incident(row) for row in rows]

    def get_stats(self, since=None):
        where = ' WHERE timestamp >= ?' if since else ''
        params = [since] if since else []
        with self.lock:
            total = self.conn.execute('SELECT COUNT(*) FROM incidents' + where, params).fetchone()[0]
            attacks = self.conn.execute('SELECT COUNT(*) FROM incidents' + (' WHERE is_attack = 1 AND timestamp >= ?' if since else ' WHERE is_attack = 1'), params).fetchone()[0]
            blocked = self.conn.execute('SELECT COUNT(*) FROM blocked_ips').fetchone()[0]
        return {
            'total_incidents': total,
            'attacks_detected': attacks,
            'ips_blocked': blocked,
            'simulation_mode': self.use_aws,
        }

    def list_blocked(self):
        with self.lock:
            rows = self.conn.execute('SELECT * FROM blocked_ips ORDER BY blocked_at DESC').fetchall()
        return [dict(row) for row in rows]

    def block_ip(self, ip, risk, reason, automatic=False):
        blocked_at = datetime.now(timezone.utc).isoformat()
        enforcement = self.firewall.block(ip)
        with self.lock, self.conn:
            self.conn.execute('''
                INSERT INTO blocked_ips (ip, blocked_at, risk, reason, automatic)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET risk=excluded.risk, reason=excluded.reason
            ''', (ip, blocked_at, risk, reason, 1 if automatic else 0))
        return {'ip': ip, 'blocked_at': blocked_at, 'risk': risk, 'reason': reason, 'automatic': automatic, 'enforcement': enforcement}

    def unblock_ip(self, ip):
        self.firewall.unblock(ip)
        with self.lock, self.conn:
            cursor = self.conn.execute('DELETE FROM blocked_ips WHERE ip = ?', (ip,))
        return cursor.rowcount > 0

    def clear_blocks(self):
        self.firewall.clear()
        with self.lock, self.conn:
            self.conn.execute('DELETE FROM blocked_ips')

    def firewall_status(self):
        return self.firewall.status()

    def log_notification(self, channel, severity, message, status='Sent'):
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.lock, self.conn:
            cursor = self.conn.execute('''
                INSERT INTO notifications (timestamp, channel, severity, message, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, channel, severity, message, status))
        return {'id': cursor.lastrowid, 'timestamp': timestamp, 'channel': channel, 'severity': severity, 'message': message, 'status': status}

    def get_notifications(self, limit=20):
        with self.lock:
            rows = self.conn.execute('SELECT * FROM notifications ORDER BY id DESC LIMIT ?', (max(1, min(int(limit), 100)),)).fetchall()
        return [dict(row) for row in rows]

    def query_incidents(self, source_ip=None, attacks_only=False, limit=100):
        clauses = []
        params = []
        if source_ip:
            clauses.append('source_ip = ?')
            params.append(source_ip)
        if attacks_only:
            clauses.append('is_attack = 1')
        query = 'SELECT * FROM incidents'
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY id DESC LIMIT ?'
        params.append(max(1, min(int(limit), 1000)))
        with self.lock:
            rows = self.conn.execute(query, params).fetchall()
        return [self._incident(row) for row in rows]

    def search_incidents(self, filters=None, group_by=None, sort_field=None, descending=False, limit=100, since=None):
        filters = filters or []
        allowed_fields = {'source_ip', 'is_attack', 'risk_level', 'confidence', 'timestamp'}
        clauses = []
        params = []
        for field, operator, value in filters:
            if field not in allowed_fields or operator not in {'=', '!=', '>=', '<=', '>', '<'}:
                raise ValueError('Unsupported search field or operator')
            clauses.append(f'{field} {operator} ?')
            params.append(value)
        if since:
            clauses.append('timestamp >= ?')
            params.append(since)

        group_expression = None
        if group_by:
            if group_by == 'attack_type':
                group_expression = "CASE WHEN is_attack = 1 THEN 'ATTACK' ELSE 'NORMAL' END"
            elif group_by in {'source_ip', 'risk_level', 'is_attack'}:
                group_expression = group_by
            else:
                raise ValueError('Unsupported stats field')

        if group_expression:
            select = f'{group_expression} AS group_value, COUNT(*) AS count'
            query = f'SELECT {select} FROM incidents'
            if clauses:
                query += ' WHERE ' + ' AND '.join(clauses)
            query += f' GROUP BY {group_expression}'
            query += ' ORDER BY count DESC, group_value ASC'
            params.append(max(1, min(int(limit), 1000)))
            query += ' LIMIT ?'
        else:
            query = 'SELECT * FROM incidents'
            if clauses:
                query += ' WHERE ' + ' AND '.join(clauses)
            order = sort_field if sort_field in allowed_fields else 'id'
            query += f' ORDER BY {order} ' + ('DESC' if descending else 'ASC')
            params.append(max(1, min(int(limit), 1000)))
            query += ' LIMIT ?'
        with self.lock:
            rows = self.conn.execute(query, params).fetchall()
        if group_expression:
            return [{'group': row['group_value'], 'count': row['count']} for row in rows]
        return [self._incident(row) for row in rows]

    @staticmethod
    def _incident(row):
        return {
            'id': row['id'],
            'timestamp': row['timestamp'],
            'source_ip': row['source_ip'],
            'is_attack': bool(row['is_attack']),
            'confidence': row['confidence'],
            'risk_level': row['risk_level'],
            'model_votes': row['model_votes'],
        }
