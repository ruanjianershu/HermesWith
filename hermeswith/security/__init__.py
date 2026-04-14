"""Security module for HermesWith - Authentication, Authorization, and Encryption."""

from hermeswith.security.auth import (
    JWTAuth,
    APIKeyAuth,
    require_auth,
    require_company_access,
    get_current_company,
    hash_api_key,
    verify_api_key,
)
from hermeswith.security.encryption import EncryptionManager, get_encryption_manager
from hermeswith.security.rate_limit import RateLimiter, get_rate_limiter, check_rate_limit, record_request
from hermeswith.security.audit import AuditLogger, get_audit_logger

__all__ = [
    "JWTAuth",
    "APIKeyAuth",
    "require_auth",
    "require_company_access",
    "get_current_company",
    "hash_api_key",
    "verify_api_key",
    "EncryptionManager",
    "get_encryption_manager",
    "RateLimiter",
    "get_rate_limiter",
    "check_rate_limit",
    "record_request",
    "AuditLogger",
    "get_audit_logger",
]
