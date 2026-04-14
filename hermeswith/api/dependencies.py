"""FastAPI dependencies for authentication and database."""

from typing import List, Optional
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from hermeswith.persistence.database import get_db as _get_db
from hermeswith.persistence.models import APIKeyDB, CompanyDB
from hermeswith.security.auth import verify_api_key
from hermeswith.security.rate_limit import check_rate_limit


security = HTTPBearer(auto_error=False)


async def get_db() -> Session:
    """Get database session."""
    db = _get_db()
    try:
        yield db
    finally:
        db.close()


async def get_current_company(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db),
) -> CompanyDB:
    """Extract and validate company from API key.
    
    Args:
        request: FastAPI request object
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        CompanyDB: The authenticated company
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    api_key = credentials.credentials
    
    # Verify API key and get company
    company = verify_api_key(db, api_key)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not company.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company account is deactivated",
        )
    
    # Check rate limit
    allowed, retry_after = check_rate_limit(company.id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds",
            headers={"Retry-After": str(retry_after)},
        )
    
    # Store company in request state for middleware
    request.state.company = company
    request.state.company_id = company.id
    
    return company


def require_permissions(required_permissions: List[str]):
    """Dependency factory to check API key permissions.
    
    Args:
        required_permissions: List of required permission strings
        
    Returns:
        Dependency function that validates permissions
    """
    async def check_permissions(
        request: Request,
        company: CompanyDB = Depends(get_current_company),
        db: Session = Depends(get_db),
    ) -> CompanyDB:
        """Check if API key has required permissions."""
        # Get API key from request
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )
        
        api_key = auth_header[7:]  # Remove "Bearer "
        
        # Find API key record
        from hermeswith.security.auth import hash_api_key
        key_hash = hash_api_key(api_key)
        
        api_key_record = (
            db.query(APIKeyDB)
            .filter(
                APIKeyDB.key_hash == key_hash,
                APIKeyDB.is_active == True,
            )
            .first()
        )
        
        if not api_key_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key not found",
            )
        
        # Check permissions
        key_permissions = set(api_key_record.permissions or [])
        required = set(required_permissions)
        
        if not required.issubset(key_permissions):
            missing = required - key_permissions
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing)}",
            )
        
        return company
    
    return check_permissions
