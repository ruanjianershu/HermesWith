"""Agent service for managing agents."""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from hermeswith.integrations.clawith_client import ClawithClient
from hermeswith.integrations.sync_service import SyncService
from hermeswith.persistence.models import AgentDB

logger = logging.getLogger(__name__)


class AgentService:
    """Service for agent management."""
    
    def __init__(
        self,
        db: Session,
        clawith_client: Optional[ClawithClient] = None,
    ):
        """Initialize agent service.
        
        Args:
            db: Database session
            clawith_client: Optional Clawith client for sync
        """
        self.db = db
        self.clawith = clawith_client
        self.sync_service = SyncService(db, clawith_client) if clawith_client else None
    
    def create_agent(
        self,
        company_id: UUID,
        name: str,
        model: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> AgentDB:
        """Create a new agent.
        
        Args:
            company_id: Company ID
            name: Agent name
            model: Model identifier
            system_prompt: System prompt
            tools: List of tool names
            
        Returns:
            Created AgentDB instance
        """
        agent = AgentDB(
            company_id=company_id,
            name=name,
            model=model,
            system_prompt=system_prompt,
            tools=tools or [],
            is_active=True,
        )
        
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        
        logger.info(f"Created agent {agent.id} for company {company_id}")
        
        # Sync to Clawith if client available
        if self.sync_service:
            try:
                import asyncio
                asyncio.create_task(self.sync_service.sync_agent_to_clawith(agent))
            except Exception as e:
                logger.warning(f"Failed to queue agent sync: {e}")
        
        return agent
    
    def get_agent(
        self,
        company_id: UUID,
        agent_id: UUID,
    ) -> Optional[AgentDB]:
        """Get an agent by ID.
        
        Args:
            company_id: Company ID
            agent_id: Agent ID
            
        Returns:
            AgentDB if found, None otherwise
        """
        return self.db.query(AgentDB).filter(
            AgentDB.id == agent_id,
            AgentDB.company_id == company_id,
        ).first()
    
    def list_agents(
        self,
        company_id: UUID,
        filters: Optional[Dict] = None,
    ) -> List[AgentDB]:
        """List agents for a company.
        
        Args:
            company_id: Company ID
            filters: Optional filters (is_active, etc.)
            
        Returns:
            List of AgentDB instances
        """
        query = self.db.query(AgentDB).filter(
            AgentDB.company_id == company_id,
        )
        
        if filters:
            if "is_active" in filters and filters["is_active"] is not None:
                query = query.filter(AgentDB.is_active == filters["is_active"])
        
        return query.order_by(AgentDB.created_at.desc()).all()
    
    def update_agent(
        self,
        company_id: UUID,
        agent_id: UUID,
        updates: Dict,
    ) -> Optional[AgentDB]:
        """Update an agent.
        
        Args:
            company_id: Company ID
            agent_id: Agent ID
            updates: Dictionary of fields to update
            
        Returns:
            Updated AgentDB if found, None otherwise
        """
        agent = self.get_agent(company_id, agent_id)
        
        if not agent:
            return None
        
        # Update allowed fields
        allowed_fields = ["name", "system_prompt", "tools", "is_active"]
        for field in allowed_fields:
            if field in updates:
                setattr(agent, field, updates[field])
        
        self.db.commit()
        self.db.refresh(agent)
        
        logger.info(f"Updated agent {agent_id} for company {company_id}")
        
        return agent
    
    def delete_agent(
        self,
        company_id: UUID,
        agent_id: UUID,
    ) -> bool:
        """Delete an agent (soft delete).
        
        Args:
            company_id: Company ID
            agent_id: Agent ID
            
        Returns:
            True if deleted, False if not found
        """
        agent = self.get_agent(company_id, agent_id)
        
        if not agent:
            return False
        
        # Soft delete
        agent.is_active = False
        self.db.commit()
        
        logger.info(f"Deleted agent {agent_id} for company {company_id}")
        
        # Also delete from Clawith if synced
        if self.clawith and agent.clawith_agent_id:
            try:
                import asyncio
                asyncio.create_task(self.clawith.delete_agent(agent.clawith_agent_id))
            except Exception as e:
                logger.warning(f"Failed to delete agent from Clawith: {e}")
        
        return True
    
    def get_agent_by_clawith_id(
        self,
        company_id: UUID,
        clawith_agent_id: str,
    ) -> Optional[AgentDB]:
        """Get agent by Clawith agent ID.
        
        Args:
            company_id: Company ID
            clawith_agent_id: Clawith agent ID
            
        Returns:
            AgentDB if found, None otherwise
        """
        return self.db.query(AgentDB).filter(
            AgentDB.clawith_agent_id == clawith_agent_id,
            AgentDB.company_id == company_id,
        ).first()
