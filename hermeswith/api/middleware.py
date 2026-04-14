"""FastAPI middleware for audit logging, rate limiting, and tenant isolation."""

import time
from typing import Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from hermeswith.security.audit import AuditLogger
from hermeswith.security.rate_limit import check_rate_limit, record_request


# Global audit logger instance
_audit_logger = AuditLogger()


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests to audit log."""
    
    def __init__(self, app: ASGIApp, db_session_factory=None):
        super().__init__(app)
        self.db_session_factory = db_session_factory
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and log to audit."""
        start_time = time.time()
        
        # Get company from request state (set by auth dependency)
        company_id = getattr(request.state, "company_id", None)
        api_key_id = getattr(request.state, "api_key_id", None)
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as e:
            status_code = 500
            error = str(e)
            raise
        finally:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log to audit
            try:
                await _audit_logger.log_request(
                    request=request,
                    company_id=str(company_id) if company_id else None,
                    api_key_id=str(api_key_id) if api_key_id else None,
                    duration_ms=duration_ms,
                )
            except Exception:
                # Audit logging should not break the request
                pass
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits per company."""
    
    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Check rate limit before processing request."""
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        # Get company from request state
        company_id = getattr(request.state, "company_id", None)
        
        if company_id:
            allowed, retry_after = check_rate_limit(
                company_id,
                max_requests=self.requests_per_minute,
            )
            
            if not allowed:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            
            # Record this request
            record_request(company_id)
        
        return await call_next(request)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure tenant isolation.
    
    This middleware adds the company_id to request state so that
    downstream code can automatically filter queries.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Add tenant context to request."""
        # Company is already set by auth dependency
        # This middleware ensures it's available for all routes
        
        # For non-authenticated routes, company_id will be None
        if not hasattr(request.state, "company_id"):
            request.state.company_id = None
        
        return await call_next(request)


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request timing headers."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Add timing information to response."""
        start_time = time.time()
        
        response = await call_next(request)
        
        duration_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        
        return response
