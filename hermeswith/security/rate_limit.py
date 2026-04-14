"""Rate limiting module for HermesWith - Redis-backed rate limiter."""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from functools import wraps
from enum import Enum

import redis.asyncio as redis
from fastapi import HTTPException, Request


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


class RateLimitConfig:
    """Configuration for rate limiting."""
    
    # Default limits per endpoint (requests per window)
    DEFAULT_LIMITS = {
        "default": {"requests": 100, "window": 60},  # 100 req/min
        "auth": {"requests": 10, "window": 60},      # 10 req/min for auth
        "create": {"requests": 20, "window": 60},    # 20 creations/min
        "execute": {"requests": 30, "window": 60},   # 30 executions/min
        "websocket": {"requests": 1000, "window": 60}, # 1000 ws connections/min
    }
    
    def __init__(self, endpoint: str = "default"):
        self.config = self.DEFAULT_LIMITS.get(endpoint, self.DEFAULT_LIMITS["default"])
        self.requests = self.config["requests"]
        self.window = self.config["window"]  # seconds


class RateLimiter:
    """
    Redis-backed rate limiter with multiple strategies.
    Supports per-API-key and per-endpoint rate limiting.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize rate limiter with Redis connection."""
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis: Optional[redis.Redis] = None
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str = "default",
        requests: int = 100,
        window: int = 60,
        strategy: RateLimitStrategy = RateLimitStrategy.FIXED_WINDOW,
    ) -> Dict[str, Any]:
        """Check if request is within rate limit.
        
        Args:
            identifier: Unique identifier (e.g., API key ID)
            endpoint: Endpoint being accessed
            requests: Maximum requests allowed in window
            window: Time window in seconds
            strategy: Rate limiting strategy to use
            
        Returns:
            Dict with allowed, remaining, reset_time, etc.
        """
        key = f"rate_limit:{endpoint}:{identifier}"
        now = time.time()
        
        try:
            r = await self._get_redis()
            
            if strategy == RateLimitStrategy.FIXED_WINDOW:
                # Fixed window: count requests in current window
                window_start = int(now // window) * window
                window_key = f"{key}:{window_start}"
                
                current = await r.get(window_key)
                current_count = int(current) if current else 0
                
                if current_count >= requests:
                    reset_time = window_start + window
                    return {
                        "allowed": False,
                        "limit": requests,
                        "remaining": 0,
                        "reset_time": reset_time,
                        "retry_after": int(reset_time - now),
                    }
                
                # Increment counter
                pipe = r.pipeline()
                pipe.incr(window_key)
                pipe.expire(window_key, window)
                await pipe.execute()
                
                return {
                    "allowed": True,
                    "limit": requests,
                    "remaining": requests - current_count - 1,
                    "reset_time": window_start + window,
                }
            
            elif strategy == RateLimitStrategy.SLIDING_WINDOW:
                # Sliding window: use sorted set of timestamps
                window_start = now - window
                
                # Remove old entries
                await r.zremrangebyscore(key, 0, window_start)
                
                # Count current requests
                current_count = await r.zcard(key)
                
                if current_count >= requests:
                    # Get oldest request to calculate retry_after
                    oldest = await r.zrange(key, 0, 0, withscores=True)
                    retry_after = int(oldest[0][1] + window - now) if oldest else window
                    
                    return {
                        "allowed": False,
                        "limit": requests,
                        "remaining": 0,
                        "reset_time": int(now + retry_after),
                        "retry_after": retry_after,
                    }
                
                # Add current request
                await r.zadd(key, {str(now): now})
                await r.expire(key, window)
                
                return {
                    "allowed": True,
                    "limit": requests,
                    "remaining": requests - current_count - 1,
                    "reset_time": int(now + window),
                }
            
            else:
                # Default: allow request
                return {
                    "allowed": True,
                    "limit": requests,
                    "remaining": requests - 1,
                    "reset_time": int(now + window),
                }
                
        except Exception as e:
            # If Redis fails, allow the request (fail open)
            return {
                "allowed": True,
                "limit": requests,
                "remaining": requests - 1,
                "reset_time": int(now + window),
            }
    
    async def reset_rate_limit(self, identifier: str, endpoint: str = "default") -> bool:
        """Reset rate limit counter for an identifier."""
        try:
            r = await self._get_redis()
            key = f"rate_limit:{endpoint}:{identifier}"
            await r.delete(key)
            return True
        except Exception:
            return False
    
    def limit(
        self,
        requests: int = 100,
        window: int = 60,
        endpoint: str = None,
        key_func: Callable = None,
    ):
        """Decorator for rate limiting.
        
        Usage:
            @app.get("/api/protected")
            @limiter.limit(requests=10, window=60)
            async def protected_endpoint(request: Request):
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                request = kwargs.get("request")
                if not request and args:
                    # Try to find request in args
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break
                
                # Get identifier
                if key_func:
                    identifier = key_func(request)
                elif request:
                    # Try to get from company/API key
                    company = kwargs.get("company")
                    if company and company.get("key_id"):
                        identifier = company["key_id"]
                    else:
                        identifier = request.client.host if request.client else "unknown"
                else:
                    identifier = "unknown"
                
                ep = endpoint or (request.url.path if request else "default")
                
                result = await self.check_rate_limit(identifier, ep, requests, window)
                
                if not result["allowed"]:
                    retry_after = result.get("retry_after", window)
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "Rate limit exceeded",
                            "retry_after": retry_after,
                            "limit": result["limit"],
                        },
                        headers={
                            "Retry-After": str(retry_after),
                            "X-RateLimit-Limit": str(result["limit"]),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(result["reset_time"]),
                        }
                    )
                
                # Store rate limit info in request state for response headers
                if request:
                    request.state.rate_limit = result
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(redis_url: Optional[str] = None) -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(redis_url)
    return _rate_limiter


def check_rate_limit(identifier: str, endpoint: str = "default", requests: int = 100, window: int = 60) -> Dict[str, Any]:
    """Check rate limit for an identifier.
    
    This is a synchronous wrapper for the async rate limiter.
    
    Args:
        identifier: Unique identifier (e.g., API key ID)
        endpoint: Endpoint being accessed
        requests: Maximum requests allowed in window
        window: Time window in seconds
        
    Returns:
        Dict with allowed, remaining, reset_time, etc.
    """
    import asyncio
    limiter = get_rate_limiter()
    try:
        return asyncio.run(limiter.check_rate_limit(identifier, endpoint, requests, window))
    except Exception:
        # If Redis is not available, allow the request
        return {
            "allowed": True,
            "limit": requests,
            "remaining": requests - 1,
            "reset_time": int(time.time()) + window,
        }


def record_request(identifier: str) -> None:
    """Record a request for rate limiting (no-op for now)."""
    pass


async def rate_limit_middleware(request: Request, call_next):
    """
    Global rate limiting middleware.
    Apply to FastAPI app with: app.middleware("http")(rate_limit_middleware)
    """
    limiter = get_rate_limiter()
    
    # Skip rate limiting for certain paths
    if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # Get identifier
    company = getattr(request.state, "company", None)
    if company and company.get("key_id"):
        identifier = company["key_id"]
    else:
        identifier = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    
    # Determine limit based on endpoint
    path = request.url.path
    if "/auth" in path:
        config = RateLimitConfig("auth")
    elif "/create" in path or request.method == "POST":
        config = RateLimitConfig("create")
    elif "/execute" in path:
        config = RateLimitConfig("execute")
    else:
        config = RateLimitConfig("default")
    
    result = await limiter.check_rate_limit(
        identifier,
        path,
        config.requests,
        config.window
    )
    
    # Process request
    response = await call_next(request)
    
    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(result["limit"])
    response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
    response.headers["X-RateLimit-Reset"] = str(result["reset_time"])
    
    if not result["allowed"]:
        from starlette.responses import JSONResponse
        retry_after = result.get("retry_after", config.window)
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "retry_after": retry_after},
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(result["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result["reset_time"]),
            }
        )
    
    return response
