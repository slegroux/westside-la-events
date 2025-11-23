"""
Security middleware and utilities for the Westside LA Events app.

This module provides:
- Rate limiting to prevent abuse
- Admin authentication
- Security headers
- Input sanitization
"""

import os
import hashlib
import hmac
from functools import wraps
from typing import Callable, Optional
from fasthtml.common import *
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import html

# ============================================================================
# Rate Limiting
# ============================================================================

limiter = Limiter(key_func=get_remote_address)

def get_limiter():
    """Get the rate limiter instance."""
    return limiter


# ============================================================================
# Admin Authentication
# ============================================================================

# Simple password-based auth for admin endpoints
# In production, use environment variable for password
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH', None)

# Default password for development (hash of "admin123")
# Generate with: python -c "import hashlib; print(hashlib.sha256('admin123'.encode()).hexdigest())"
DEFAULT_PASSWORD_HASH = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"

def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hmac.compare_digest(hash_password(password), password_hash)

def check_admin_auth(request: Request) -> bool:
    """
    Check if the user is authenticated as admin.
    Uses session-based authentication.
    """
    session = request.session if hasattr(request, 'session') else {}
    return session.get('admin_authenticated', False) is True

def require_admin(func: Callable):
    """
    Decorator to require admin authentication for a route.
    Redirects to login page if not authenticated.
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not check_admin_auth(request):
            # Redirect to login page
            return RedirectResponse(
                url=f'/admin/login?redirect={request.url.path}',
                status_code=303
            )
        return await func(request, *args, **kwargs)
    return wrapper


# ============================================================================
# Security Headers Middleware
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # CSP - allow maps, fonts, and inline scripts (needed for FastHTML)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self' https:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' https:; "
        )

        return response


# ============================================================================
# Input Sanitization
# ============================================================================

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent XSS and other attacks.

    Args:
        text: The input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text with HTML escaped and length limited
    """
    if not text:
        return ""

    # Limit length
    text = text[:max_length]

    # HTML escape
    text = html.escape(text)

    # Remove null bytes
    text = text.replace('\x00', '')

    return text.strip()


def sanitize_search_params(params: dict) -> dict:
    """
    Sanitize search parameters from user input.

    Args:
        params: Dictionary of search parameters

    Returns:
        Dictionary with sanitized values
    """
    sanitized = {}

    # Sanitize text fields
    text_fields = ['q', 'search', 'query', 'keyword']
    for field in text_fields:
        if field in params:
            sanitized[field] = sanitize_input(params[field], max_length=200)

    # Validate category (whitelist)
    if 'category' in params:
        allowed_categories = [
            'music', 'art', 'food', 'sports', 'family', 'theater',
            'film', 'comedy', 'outdoors', 'nightlife', 'education', 'other'
        ]
        category = params['category'].lower().strip()
        if category in allowed_categories:
            sanitized['category'] = category

    # Validate date format (YYYY-MM-DD)
    date_fields = ['start_date', 'end_date', 'date']
    for field in date_fields:
        if field in params:
            date_str = params[field]
            # Simple validation - should be YYYY-MM-DD format
            if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
                try:
                    year, month, day = date_str.split('-')
                    if year.isdigit() and month.isdigit() and day.isdigit():
                        sanitized[field] = date_str
                except:
                    pass

    return sanitized


# ============================================================================
# Security Configuration
# ============================================================================

def get_admin_password_hash() -> str:
    """Get the admin password hash from environment or use default."""
    return ADMIN_PASSWORD_HASH or DEFAULT_PASSWORD_HASH

def is_production() -> bool:
    """Check if running in production mode."""
    return os.getenv('ENV', 'development').lower() == 'production'

def get_rate_limits():
    """
    Get rate limit configuration.

    Returns:
        Dictionary with rate limits for different endpoint types
    """
    return {
        'default': '100/minute',  # General endpoints
        'search': '30/minute',     # Search queries
        'api': '60/minute',        # API endpoints
        'admin': '20/minute',      # Admin endpoints
        'scraper': '10/hour',      # Scraper trigger (very restrictive)
    }
