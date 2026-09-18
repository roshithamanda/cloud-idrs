"""Local firewall enforcement for CIDRS response actions."""

from __future__ import annotations

import ipaddress
import os
import shutil
import subprocess


class FirewallProvider:
    """Apply CIDRS-owned nftables rules when explicitly enabled."""

    TABLE = 'cidrs_filter'
    CHAIN = 'cidrs_input'

    def __init__(self, mode=None):
        self.mode = (mode or os.getenv('CIDRS_FIREWALL_MODE', 'database')).lower()
        self.nft = shutil.which('nft')

    @property
    def enabled(self):
        return self.mode == 'nft'

    def status(self):
        return {'mode': self.mode, 'enabled': self.enabled, 'available': bool(self.nft), 'enforced': self.enabled and bool(self.nft)}

    def block(self, ip):
        self._validate(ip)
        if not self.enabled:
            return {'enforced': False, 'reason': 'CIDRS_FIREWALL_MODE is not nft'}
        self._ensure_table()
        family = 'ip6' if ':' in ip else 'ip'
        self._run(['add', 'rule', 'inet', self.TABLE, self.CHAIN, family, 'saddr', ip, 'drop'])
        return {'enforced': True, 'provider': 'nftables'}

    def unblock(self, ip):
        self._validate(ip)
        if not self.enabled:
            return {'enforced': False, 'reason': 'CIDRS_FIREWALL_MODE is not nft'}
        listing = self._run(['-a', 'list', 'chain', 'inet', self.TABLE, self.CHAIN], check=False)
        family = 'ip6' if ':' in ip else 'ip'
        for line in listing.stdout.splitlines():
            if f'{family} saddr {ip} drop' not in line or '# handle ' not in line:
                continue
            handle = line.rsplit('# handle ', 1)[1].split()[0]
            self._run(['delete', 'rule', 'inet', self.TABLE, self.CHAIN, 'handle', handle])
        return {'enforced': True, 'provider': 'nftables'}

    def clear(self):
        if not self.enabled:
            return {'enforced': False, 'reason': 'CIDRS_FIREWALL_MODE is not nft'}
        self._run(['flush', 'chain', 'inet', self.TABLE, self.CHAIN], check=False)
        return {'enforced': True, 'provider': 'nftables'}

    def _ensure_table(self):
        self._run(['add', 'table', 'inet', self.TABLE], check=False)
        self._run(['add', 'chain', 'inet', self.TABLE, self.CHAIN, '{', 'type', 'filter', 'hook', 'input', 'priority', '0', ';', 'policy', 'accept', ';', '}'], check=False)

    def _run(self, args, check=True):
        if not self.nft:
            raise RuntimeError('nft command is unavailable')
        try:
            return subprocess.run(['sudo', '-n', self.nft, *args], check=check, capture_output=True, text=True, timeout=5)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(exc.stderr.strip() or 'nftables command failed') from exc
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError(str(exc)) from exc

    @staticmethod
    def _validate(ip):
        ipaddress.ip_address(ip)
