"""
CIDRS Response Engine
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

class ResponseEngine:
    def __init__(self, use_aws=False):
        self.use_aws = use_aws
        self.blocked_ips = set()
        self.init_database()
    
    def init_database(self):
        db_path = Path('data/incidents.db')
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect('data/incidents.db')
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                source_ip TEXT,
                is_attack INTEGER,
                confidence REAL,
                risk_level TEXT
            )
        ''')
        self.conn.commit()
    
    def log_incident(self, incident):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO incidents (timestamp, source_ip, is_attack, confidence, risk_level)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            incident.get('timestamp', datetime.now().isoformat()),
            incident.get('source_ip', 'unknown'),
            1 if incident.get('is_attack') else 0,
            incident.get('confidence', 0),
            incident.get('risk_level', 'LOW')
        ))
        self.conn.commit()
        return {'status': 'logged', 'incident_id': cursor.lastrowid}
    
    def get_recent_incidents(self, limit=50):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, timestamp, source_ip, is_attack, confidence, risk_level FROM incidents ORDER BY id DESC LIMIT ?', (limit,))
        incidents = []
        for row in cursor.fetchall():
            incidents.append({
                'id': row[0],
                'timestamp': row[1],
                'source_ip': row[2],
                'is_attack': bool(row[3]),
                'confidence': row[4],
                'risk_level': row[5]
            })
        return incidents
    
    def get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM incidents')
        total = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM incidents WHERE is_attack = 1')
        attacks = cursor.fetchone()[0]
        return {
            'total_incidents': total,
            'attacks_detected': attacks,
            'ips_blocked': 0,
            'simulation_mode': self.use_aws
        }
