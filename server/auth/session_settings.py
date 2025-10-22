"""Shared session configuration and helpers for auth providers."""
from __future__ import annotations

import os
from typing import Optional

SESSION_COOKIE = os.environ.get('SESSION_COOKIE_NAME', 'app_session')
SESSION_MIN_SECONDS = int(os.environ.get('SESSION_MIN_SECONDS', '0') or '0')
SESSION_TTL_DEFAULT = int(os.environ.get('SESSION_TTL_DEFAULT', '3600') or '3600')

SESSION_COOKIE_SECURE = (
    os.environ.get('APP_ENV', '').lower() in ('prod', 'production')
    or os.environ.get('SESSION_COOKIE_SECURE', '0') in ('1', 'true', 'yes')
)
SESSION_COOKIE_DOMAIN_RAW = os.environ.get('SESSION_COOKIE_DOMAIN', '').strip()
SESSION_COOKIE_DOMAINS = [
    d.strip() for d in SESSION_COOKIE_DOMAIN_RAW.split(',') if d.strip()
] if SESSION_COOKIE_DOMAIN_RAW else []
SESSION_COOKIE_DOMAIN_SINGLE = SESSION_COOKIE_DOMAINS[0] if len(SESSION_COOKIE_DOMAINS) == 1 else ''


def select_cookie_domain(host: Optional[str]) -> str:
    """Pick an appropriate cookie domain for the provided host."""
    if not SESSION_COOKIE_DOMAINS:
        return ''
    if len(SESSION_COOKIE_DOMAINS) == 1:
        return SESSION_COOKIE_DOMAINS[0]
    if not host:
        return ''
    host_l = host.lower()
    matches = [
        d for d in SESSION_COOKIE_DOMAINS
        if host_l == d.lower() or host_l.endswith('.' + d.lower())
    ]
    if not matches:
        return ''
    matches.sort(key=len, reverse=True)
    return matches[0]


__all__ = [
    'SESSION_COOKIE',
    'SESSION_MIN_SECONDS',
    'SESSION_TTL_DEFAULT',
    'SESSION_COOKIE_SECURE',
    'SESSION_COOKIE_DOMAIN_RAW',
    'SESSION_COOKIE_DOMAINS',
    'SESSION_COOKIE_DOMAIN_SINGLE',
    'select_cookie_domain',
]
