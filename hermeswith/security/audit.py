"""Audit logging module for HermesWith - Log all API requests and actions."""

import json
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from functools import wraps
from enum import Enum

from fastapi import Request, Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from hermeswith.persistence.database import AsyncSessionLocal
from hermeswith.persistence.models import AuditLogDB


class AuditAction(Enum):
    """Audit action types."""
    GOAL_CREATED = "goal_created"
    GOAL_UPDATED = "goal_updated"
    GOAL_DELETED = "goal_deleted"
    GOAL_EXECUTED = "goal_executed"
    AGENT_REGISTERED = "agent_registered"
    AGENT_PAUSED = "agent_paused"
    AGENT_RESUMED = "agent_resumed"
    AGENT_DELETED = "agent_deleted"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    CONFIG_ENCRYPTED = "config_encrypted"
    CONFIG_DECRYPTED = "config_decrypted"
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS_DENIED = "access_denied"
    RATE_LIMITED = "rate_limited"


class AuditLogger:
    """
    Audit logger for all API requests and actions.
    Stores logs in database for persistence and querying.
    """
    
    def __init__(self):
        self._buffer: List[Dict] = []
        self._buffer_size = 100
        self._flush_interval = 30  # seconds
        self._last_flush = time.time()
    
    async def log_request(
        self,
        request: Request,
        response: Optional[Response] = None,
        company_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Log an API request.
        
        Args:
            request: FastAPI request object
            response: FastAPI response object
            company_id: Company UUID
            api_key_id: API key UUID
            duration_ms: Request duration in milliseconds
            action: Action type (e.g., "goal_created")
            resource_type: Resource type (e.g., "goal")
            resource_id: Resource UUID
            metadata: Additional metadata
        """
        # Extract request info
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        
        # Sanitize request body
        request_body = None
        try:
            body = await request.body()
            if body:
                try:
                    body_json = json.loads(body)
                    # Remove sensitive fields
                    body_json = self._sanitize_body(body_json)
                    request_body = body_json
                except json.JSONDecodeError:
                    request_body = {"raw": body.decode("utf-8", errors="replace")[:1000]}
        except Exception:
            pass
        
        # Get client info
        ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
        user_agent = request.headers.get("User-Agent")
        
        # Response info
        status_code = response.status_code if response else None
        response_size = len(response.body) if response and hasattr(response, "body") else 0
        
        log_entry = {
            "company_id": company_id,
            "api_key_id": api_key_id,
            "method": method,
            "path": path,
            "query_params": query_params,
            "request_body": request_body,
            "status_code": status_code,
            "response_size": response_size,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "started_at": datetime.utcnow(),
            "duration_ms": duration_ms,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": metadata or {},
        }
        
        await self._persist_log(log_entry)
    
    async def log_action(
        self,
        action: AuditAction,
        company_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Log a specific action.
        
        Args:
            action: The action type
            company_id: Company UUID
            api_key_id: API key UUID
            resource_type: Resource type
            resource_id: Resource UUID
            metadata: Additional metadata
            ip_address: Client IP address
            user_agent: Client user agent
        """
        log_entry = {
            "company_id": company_id,
            "api_key_id": api_key_id,
            "method": "INTERNAL",
            "path": f"/action/{action.value}",
            "query_params": {},
            "request_body": None,
            "status_code": 200,
            "response_size": 0,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "started_at": datetime.utcnow(),
            "duration_ms": 0,
            "action": action.value,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": metadata or {},
        }
        
        await self._persist_log(log_entry)
    
    def _sanitize_body(self, body: Dict) -> Dict:
        """Remove sensitive fields from request body."""
        if not isinstance(body, dict):
            return body
        
        sensitive_fields = [
            "password", "secret", "token", "api_key", "key", 
            "authorization", "auth", "credential", "private_key"
        ]
        
        sanitized = {}
        for key, value in body.items():
            if any(field in key.lower() for field in sensitive_fields):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_body(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_body(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    async def _persist_log(self, log_entry: Dict) -> None:
        """Persist log entry to database."""
        async with AsyncSessionLocal() as session:
            try:
                db_log = AuditLogDB(
                    id=uuid.uuid4(),
                    company_id=uuid.UUID(log_entry["company_id"]) if log_entry.get("company_id") else None,
                    api_key_id=uuid.UUID(log_entry["api_key_id"]) if log_entry.get("api_key_id") else None,
                    method=log_entry["method"],
                    path=log_entry["path"],
                    query_params=log_entry["query_params"],
                    request_body=log_entry["request_body"],
                    status_code=log_entry["status_code"],
                    response_size=log_entry["response_size"],
                    ip_address=log_entry["ip_address"],
                    user_agent=log_entry["user_agent"],
                    started_at=log_entry["started_at"],
                    duration_ms=log_entry["duration_ms"],
                    action=log_entry["action"],
                    resource_type=log_entry["resource_type"],
                    resource_id=log_entry["resource_id"],
                    metadata=log_entry["metadata"],
                )
                session.add(db_log)
                await session.commit()
            except Exception as e:
                await session.rollback()
                # Log to stderr as fallback
                import sys
                print(f"Failed to persist audit log: {e}", file=sys.stderr)
    
    async def query_logs(
        self,
        company_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query audit logs with filters.
        
        Returns:
            List of log entries
        """
        async with AsyncSessionLocal() as session:
            stmt = select(AuditLogDB).order_by(desc(AuditLogDB.started_at))
            
            if company_id:
                stmt = stmt.where(AuditLogDB.company_id == uuid.UUID(company_id))
            if api_key_id:
                stmt = stmt.where(AuditLogDB.api_key_id == uuid.UUID(api_key_id))
            if action:
                stmt = stmt.where(AuditLogDB.action == action)
            if resource_type:
                stmt = stmt.where(AuditLogDB.resource_type == resource_type)
            if resource_id:
                stmt = stmt.where(AuditLogDB.resource_id == resource_id)
            if start_date:
                stmt = stmt.where(AuditLogDB.started_at >= start_date)
            if end_date:
                stmt = stmt.where(AuditLogDB.started_at <= end_date)
            
            stmt = stmt.offset(skip).limit(limit)
            
            result = await session.execute(stmt)
            logs = result.scalars().all()
            
            return [
                {
                    "id": str(log.id),
                    "company_id": str(log.company_id) if log.company_id else None,
                    "api_key_id": str(log.api_key_id) if log.api_key_id else None,
                    "method": log.method,
                    "path": log.path,
                    "query_params": log.query_params,
                    "request_body": log.request_body,
                    "status_code": log.status_code,
                    "response_size": log.response_size,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "started_at": log.started_at.isoformat() if log.started_at else None,
                    "duration_ms": log.duration_ms,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "metadata": log.metadata,
                }
                for log in logs
            ]
    
    async def get_log_summary(
        self,
        company_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics for audit logs."""
        from sqlalchemy import func
        
        async with AsyncSessionLocal() as session:
            stmt = select(
                func.count(AuditLogDB.id).label("total"),
                func.count(func.distinct(AuditLogDB.action)).label("unique_actions"),
                func.avg(AuditLogDB.duration_ms).label("avg_duration"),
            )
            
            if company_id:
                stmt = stmt.where(AuditLogDB.company_id == uuid.UUID(company_id))
            if start_date:
                stmt = stmt.where(AuditLogDB.started_at >= start_date)
            if end_date:
                stmt = stmt.where(AuditLogDB.started_at <= end_date)
            
            result = await session.execute(stmt)
            row = result.one()
            
            return {
                "total_requests": row.total,
                "unique_actions": row.unique_actions,
                "avg_duration_ms": round(row.avg_duration, 2) if row.avg_duration else 0,
            }


def audit_middleware(request: Request, call_next):
    """
    Audit logging middleware for FastAPI.
    Apply with: app.middleware("http")(audit_middleware)
    """
    start_time = time.time()
    
    async def middleware():
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Get company info from request state
        company = getattr(request.state, "company", None)
        company_id = company.get("company_id") if company else None
        api_key_id = company.get("key_id") if company else None
        
        # Determine action from request
        action = _determine_action(request, response)
        
        # Log the request
        logger = get_audit_logger()
        await logger.log_request(
            request=request,
            response=response,
            company_id=company_id,
            api_key_id=api_key_id,
            duration_ms=duration_ms,
            action=action,
        )
        
        return response
    
    return middleware()


def _determine_action(request: Request, response: Response) -> Optional[str]:
    """Determine the action type from request path and method."""
    path = request.url.path
    method = request.method
    
    action_map = {
        ("POST", "/api/companies"): AuditAction.GOAL_CREATED,
        ("POST", "/api/goals"): AuditAction.GOAL_CREATED,
        ("DELETE", "/api/goals"): AuditAction.GOAL_DELETED,
        ("POST", "/api/agents"): AuditAction.AGENT_REGISTERED,
        ("POST", "/api/agents/"): AuditAction.AGENT_REGISTERED,
        ("POST", "/api/agents/{}/pause"): AuditAction.AGENT_PAUSED,
        ("POST", "/api/agents/{}/resume"): AuditAction.AGENT_RESUMED,
        ("POST", "/api/agents/{}/execute"): AuditAction.GOAL_EXECUTED,
    }
    
    for (m, p), action in action_map.items():
        if method == m and path.startswith(p.replace("{}", "")):
            return action.value
    
    return None


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
