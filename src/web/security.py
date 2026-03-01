"""
Security utilities for admin routes.
"""

import base64
import hmac
from starlette.requests import Request
import config


def check_admin_auth(request: Request) -> bool:
    """
    Check if request is authenticated for admin routes via HTTP Basic Auth.

    Args:
        request: Starlette request object

    Returns:
        True if authenticated, False otherwise
    """
    # Allow temporary bypass when admin auth is disabled.
    if not config.ENABLE_ADMIN_AUTH:
        return True

    # Secure mode: require explicit credentials in environment.
    if not config.ADMIN_USERNAME or not config.ADMIN_PASSWORD:
        return False

    auth_header = request.headers.get('authorization', '')
    if not auth_header.startswith('Basic '):
        return False

    try:
        encoded = auth_header.split(' ', 1)[1].strip()
        decoded = base64.b64decode(encoded).decode('utf-8')
        username, password = decoded.split(':', 1)
    except Exception:
        return False

    return (
        hmac.compare_digest(username, config.ADMIN_USERNAME) and
        hmac.compare_digest(password, config.ADMIN_PASSWORD)
    )
