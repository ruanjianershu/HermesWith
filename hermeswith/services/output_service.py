"""Output service for managing agent outputs."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from hermeswith.integrations.clawith_client import ClawithClient
from hermeswith.integrations.sync_service import SyncService
from hermeswith.persistence.models import AgentDB, AgentOutputDB

logger = logging.getLogger(__name__)


class OutputService:
    """Service for agent output management."""
    
    def __init__(
        self,
        db: Session,
        clawith_client: Optional[ClawithClient] = None,
    ):
        """Initialize output service.
        
        Args:
            db: Database session
            clawith_client: Optional Clawith client for sync
        """
        self.db = db
        self.clawith = clawith_client
        self.sync_service = SyncService(db, clawith_client) if clawith_client else None
    
    def get_agent_outputs(
        self,
        company_id: UUID,
        agent_id: UUID,
        since: Optional[datetime] = None,
        output_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentOutputDB]:
        """Get outputs for an agent.
        
        Args:
            company_id: Company ID
            agent_id: Agent ID
            since: Only return outputs after this time
            output_type: Filter by output type
            limit: Maximum number of outputs
            
        Returns:
            List of AgentOutputDB instances
        """
        query = self.db.query(AgentOutputDB).filter(
            AgentOutputDB.agent_id == agent_id,
            AgentOutputDB.company_id == company_id,
        )
        
        if since:
            query = query.filter(AgentOutputDB.created_at > since)
        
        if output_type:
            query = query.filter(AgentOutputDB.output_type == output_type)
        
        return query.order_by(AgentOutputDB.created_at.desc()).limit(limit).all()
    
    def get_latest_output(
        self,
        company_id: UUID,
        agent_id: UUID,
    ) -> Optional[AgentOutputDB]:
        """Get the latest output for an agent.
        
        Args:
            company_id: Company ID
            agent_id: Agent ID
            
        Returns:
            Latest AgentOutputDB if any, None otherwise
        """
        return self.db.query(AgentOutputDB).filter(
            AgentOutputDB.agent_id == agent_id,
            AgentOutputDB.company_id == company_id,
        ).order_by(AgentOutputDB.created_at.desc()).first()
    
    def get_task_outputs(
        self,
        company_id: UUID,
        task_id: UUID,
    ) -> List[AgentOutputDB]:
        """Get outputs for a specific task.
        
        Args:
            company_id: Company ID
            task_id: Task ID
            
        Returns:
            List of AgentOutputDB instances
        """
        return self.db.query(AgentOutputDB).filter(
            AgentOutputDB.task_id == task_id,
            AgentOutputDB.company_id == company_id,
        ).order_by(AgentOutputDB.created_at.asc()).all()
    
    def create_output(
        self,
        company_id: UUID,
        agent_id: UUID,
        output_type: str,
        content: str,
        task_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
        clawith_output_id: Optional[str] = None,
    ) -> AgentOutputDB:
        """Create a new output record.
        
        Args:
            company_id: Company ID
            agent_id: Agent ID
            output_type: Type of output (text, json, file, etc.)
            content: Output content
            task_id: Optional associated task ID
            metadata: Optional metadata dict
            clawith_output_id: Optional Clawith output ID
            
        Returns:
            Created AgentOutputDB instance
        """
        output = AgentOutputDB(
            company_id=company_id,
            agent_id=agent_id,
            task_id=task_id,
            output_type=output_type,
            content=content,
            metadata=metadata or {},
            clawith_output_id=clawith_output_id,
        )
        
        self.db.add(output)
        self.db.commit()
        self.db.refresh(output)
        
        logger.info(f"Created output {output.id} for agent {agent_id}")
        
        return output
    
    def sync_outputs_from_clawith(
        self,
        company_id: UUID,
        agent_id: UUID,
    ) -> int:
        """Sync outputs from Clawith.
        
        Args:
            company_id: Company ID
            agent_id: Agent ID
            
        Returns:
            Number of new outputs synced
        """
        if not self.sync_service:
            logger.warning("Sync service not available")
            return 0
        
        try:
            import asyncio
            return asyncio.run(
                self.sync_service.sync_outputs_from_clawith(company_id, agent_id)
            )
        except Exception as e:
            logger.error(f"Error syncing outputs for agent {agent_id}: {e}")
            return 0
    
    def search_outputs(
        self,
        company_id: UUID,
        agent_id: Optional[UUID] = None,
        query: Optional[str] = None,
        output_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[AgentOutputDB]:
        """Search outputs with filters.
        
        Args:
            company_id: Company ID
            agent_id: Optional agent ID filter
            query: Optional text search in content
            output_type: Filter by output type
            since: Only return outputs after this time
            limit: Maximum results
            
        Returns:
            List of matching AgentOutputDB instances
        """
        db_query = self.db.query(AgentOutputDB).filter(
            AgentOutputDB.company_id == company_id,
        )
        
        if agent_id:
            db_query = db_query.filter(AgentOutputDB.agent_id == agent_id)
        
        if output_type:
            db_query = db_query.filter(AgentOutputDB.output_type == output_type)
        
        if since:
            db_query = db_query.filter(AgentOutputDB.created_at > since)
        
        if query:
            # Simple case-insensitive search
            db_query = db_query.filter(
                AgentOutputDB.content.ilike(f"%{query}%")
            )
        
        return db_query.order_by(AgentOutputDB.created_at.desc()).limit(limit).all()
    
    def delete_old_outputs(
        self,
        company_id: UUID,
        before: datetime,
        agent_id: Optional[UUID] = None,
    ) -> int:
        """Delete old outputs.
        
        Args:
            company_id: Company ID
            before: Delete outputs created before this time
            agent_id: Optional agent ID filter
            
        Returns:
            Number of outputs deleted
        """
        query = self.db.query(AgentOutputDB).filter(
            AgentOutputDB.company_id == company_id,
            AgentOutputDB.created_at < before,
        )
        
        if agent_id:
            query = query.filter(AgentOutputDB.agent_id == agent_id)
        
        count = query.delete(synchronize_session=False)
        self.db.commit()
        
        logger.info(f"Deleted {count} old outputs for company {company_id}")
        
        return count
