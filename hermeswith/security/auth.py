"""Authentication and Authorization for HermesWith Control Plane."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeswith.persistence.database import AsyncSessionLocal
from hermeswith.persistence.models import CompanyDB, APIKeyDB

# Security configuration
SECRET_KEY = secrets.token_hex(32)  # In production, load from env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
API_KEY_PREFIX = "hw_"

# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage using SHA256."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key_hash(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    return hash_api_key(plain_key) == hashed_key


def verify_api_key(db, api_key: str):
    """Verify an API key and return the associated company."""
    if not api_key:
        return None
    
    # Find API key in database
    from hermeswith.persistence.models import APIKeyDB
    
    key_hash = hash_api_key(api_key)
    key_record = db.query(APIKeyDB).filter(
        APIKeyDB.key_hash == key_hash,
        APIKeyDB.is_active == True,
        APIKeyDB.expires_at > datetime.utcnow(),
    ).first()
    
    if not key_record:
        return None
    
    # Update last used timestamp
    key_record.last_used_at = datetime.utcnow()
    db.commit()
    
    # Return company
    return db.query(CompanyDB).filter(CompanyDB.id == key_record.company_id).first()


class JWTAuth:
    """JWT Token authentication handler."""
    
    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        import jwt
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        import jwt
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != "access":
                return None
            return payload
        except Exception:
            return None


class APIKeyAuth:
    """API Key authentication handler for company-level access."""
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a new API key with prefix."""
        random_part = secrets.token_urlsafe(32)
        return f"{API_KEY_PREFIX}{random_part}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key for storage."""
        return hash_api_key(api_key)
    
    @staticmethod
    def verify_api_key(plain_key: str, hashed_key: str) -> bool:
        """Verify an API key against its hash."""
        return verify_api_key_hash(plain_key, hashed_key)
    
    @staticmethod
    async def validate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return company info."""
        if not api_key.startswith(API_KEY_PREFIX):
            return None
        
        async with AsyncSessionLocal() as session:
            # Find the API key in database
            result = await session.execute(
                select(APIKeyDB).where(
                    APIKeyDB.is_active == True,
                    APIKeyDB.expires_at > datetime.utcnow()
                )
            )
            api_keys = result.scalars().all()
            
            for key_record in api_keys:
                if verify_api_key_hash(api_key, key_record.key_hash):
                    # Update last used timestamp
                    key_record.last_used_at = datetime.utcnow()
                    await session.commit()
                    
                    return {
                        "company_id": str(key_record.company_id),
                        "key_id": str(key_record.id),
                        "name": key_record.name,
                        "permissions": key_record.permissions or ["read", "write"],
                    }
            
            return None


async def get_current_company(
    credentials: HTTPAuthorizationCredentials = Security(security),
    request: Request = None
) -> Dict[str, Any]:
    """
    Dependency to get the current authenticated company.
    Supports both JWT Bearer tokens and API Keys (via X-API-Key header).
    """
    # Try API Key from header first
    if request:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            company_info = await APIKeyAuth.validate_api_key(api_key)
            if company_info:
                return company_info
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Try JWT Bearer token
    if credentials:
        token = credentials.credentials
        payload = JWTAuth.verify_token(token)
        if payload:
            company_id = payload.get("company_id")
            if company_id:
                return {
                    "company_id": company_id,
                    "permissions": payload.get("permissions", ["read", "write"]),
                }
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    raise HTTPException(status_code=401, detail="Authentication required")


def require_auth(permissions: Optional[list] = None):
    """
    Decorator to require authentication with specific permissions.
    
    Usage:
        @app.get("/api/protected")
        @require_auth(permissions=["read"])
        async def protected_endpoint(company: dict = Depends(get_current_company)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # The actual auth check is handled by FastAPI's dependency injection
            # This decorator is for documentation and additional permission checks
            company = kwargs.get("company")
            if company and permissions:
                user_perms = set(company.get("permissions", []))
                required_perms = set(permissions)
                if not required_perms.issubset(user_perms):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Insufficient permissions. Required: {permissions}"
                    )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_company_access(target_company_param: str = "company_id"):
    """
    Decorator to ensure the authenticated company can only access its own data.
    
    Usage:
        @app.get("/api/companies/{company_id}/goals")
        @require_company_access("company_id")
        async def list_goals(company_id: str, company: dict = Depends(get_current_company)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            company = kwargs.get("company")
            target_company_id = kwargs.get(target_company_param)
            
            if company and target_company_id:
                auth_company_id = company.get("company_id")
                if auth_company_id != target_company_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied: cannot access other company's data"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class CompanyManager:
    """Manage companies and their API keys."""
    
    @staticmethod
    async def create_company(name: str, meta: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a new company with an initial API key."""
        async with AsyncSessionLocal() as session:
            company = CompanyDB(
                id=uuid.uuid4(),
                name=name,
                meta=meta or {},
            )
            session.add(company)
            await session.flush()  # Get the company ID
            
            # Generate initial API key
            api_key = APIKeyAuth.generate_api_key()
            key_hash = APIKeyAuth.hash_api_key(api_key)
            
            api_key_record = APIKeyDB(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Default API Key",
                key_hash=key_hash,
                permissions=["read", "write", "admin"],
                expires_at=datetime.utcnow() + timedelta(days=365),
            )
            session.add(api_key_record)
            await session.commit()
            
            return {
                "company_id": str(company.id),
                "name": company.name,
                "api_key": api_key,  # Only returned once on creation
                "key_id": str(api_key_record.id),
            }
    
    @staticmethod
    async def create_api_key(
        company_id: str,
        name: str,
        permissions: list = None,
        expires_days: int = 90
    ) -> Dict[str, Any]:
        """Create a new API key for a company."""
        async with AsyncSessionLocal() as session:
            api_key = APIKeyAuth.generate_api_key()
            key_hash = APIKeyAuth.hash_api_key(api_key)
            
            key_record = APIKeyDB(
                id=uuid.uuid4(),
                company_id=uuid.UUID(company_id),
                name=name,
                key_hash=key_hash,
                permissions=permissions or ["read"],
                expires_at=datetime.utcnow() + timedelta(days=expires_days),
            )
            session.add(key_record)
            await session.commit()
            
            return {
                "key_id": str(key_record.id),
                "api_key": api_key,  # Only returned once
                "name": name,
                "permissions": key_record.permissions,
                "expires_at": key_record.expires_at.isoformat(),
            }
    
    @staticmethod
    async def revoke_api_key(company_id: str, key_id: str) -> bool:
        """Revoke an API key."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(APIKeyDB).where(
                    APIKeyDB.id == uuid.UUID(key_id),
                    APIKeyDB.company_id == uuid.UUID(company_id)
                )
            )
            key_record = result.scalar_one_or_none()
            
            if key_record:
                key_record.is_active = False
                key_record.revoked_at = datetime.utcnow()
                await session.commit()
                return True
            return False
    
    @staticmethod
    async def list_api_keys(company_id: str) -> list:
        """List all API keys for a company (without the actual keys)."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(APIKeyDB).where(
                    APIKeyDB.company_id == uuid.UUID(company_id),
                    APIKeyDB.is_active == True
                )
            )
            keys = result.scalars().all()
            
            return [
                {
                    "key_id": str(k.id),
                    "name": k.name,
                    "permissions": k.permissions,
                    "created_at": k.created_at.isoformat() if k.created_at else None,
                    "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                    "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                }
                for k in keys
            ]
