"""Synchronization service for Clawith integration."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from hermeswith.integrations.clawith_client import ClawithClient
from hermeswith.persistence.models import AgentDB, AgentOutputDB, TaskDB

logger = logging.getLogger(__name__)


class SyncService:
    """Service for synchronizing data with Clawith."""
    
    def __init__(
        self,
        db: Session,
        clawith_client: Optional[ClawithClient] = None,
    ):
        """Initialize sync service.
        
        Args:
            db: Database session
            clawith_client: Clawith API client
        """
        self.db = db
        self.clawith = clawith_client
    
    async def sync_agent_to_clawith(
        self,
        agent_db: AgentDB,
    ) -> Optional[str]:
        """Sync agent to Clawith.
        
        Creates or updates agent in Clawith.
        
        Args:
            agent_db: Agent database model
            
        Returns:
            Clawith agent ID if successful
        """
        if not self.clawith:
            logger.warning("Clawith client not configured")
            return None
        
        try:
            # If agent already has a Clawith ID, update it
            if agent_db.clawith_agent_id:
                # TODO: Implement update logic when Clawith supports it
                return agent_db.clawith_agent_id
            
            # Create new agent in Clawith
            clawith_agent_id = await self.clawith.create_agent(
                name=agent_db.name,
                model=agent_db.model,
                system_prompt=agent_db.system_prompt,
                tools=agent_db.tools,
                company_id=agent_db.company_id,
            )
            
            # Update local record
            agent_db.clawith_agent_id = clawith_agent_id
            agent_db.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(
                f"Created agent in Clawith: {clawith_agent_id} "
                f"for company {agent_db.company_id}"
            )
            
            return clawith_agent_id
            
        except Exception as e:
            logger.error(f"Failed to sync agent to Clawith: {e}")
            self.db.rollback()
            raise
    
    async def sync_task_to_clawith(
        self,
        task_db: TaskDB,
    ) -> Optional[str]:
        """Sync task to Clawith.
        
        Assigns task to agent in Clawith.
        
        Args:
            task_db: Task database model
            
        Returns:
            Clawith task ID if successful
        """
        if not self.clawith:
            logger.warning("Clawith client not configured")
            return None
        
        # Get agent
        agent = self.db.query(AgentDB).filter(
            AgentDB.id == task_db.agent_id,
            AgentDB.company_id == task_db.company_id,
        ).first()
        
        if not agent:
            raise ValueError(f"Agent {task_db.agent_id} not found")
        
        if not agent.clawith_agent_id:
            # Sync agent first
            await self.sync_agent_to_clawith(agent)
        
        if not agent.clawith_agent_id:
            raise ValueError(f"Failed to sync agent {agent.id} to Clawith")
        
        try:
            # Create task in Clawith
            task_data = {
                "title": task_db.title,
                "description": task_db.description or "",
                "instruction": task_db.instruction,
                "priority": task_db.priority,
                "metadata": {
                    "company_id": str(task_db.company_id),
                    "task_id": str(task_db.id),
                },
            }
            
            clawith_task_id = await self.clawith.assign_task(
                agent_id=agent.clawith_agent_id,
                task_data=task_data,
            )
            
            # Update local record
            task_db.clawith_task_id = clawith_task_id
            task_db.status = "pending"
            task_db.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(
                f"Created task in Clawith: {clawith_task_id} "
                f"for agent {agent.clawith_agent_id}"
            )
            
            return clawith_task_id
            
        except Exception as e:
            logger.error(f"Failed to sync task to Clawith: {e}")
            self.db.rollback()
            raise
    
    async def sync_task_from_clawith(
        self,
        task_id: UUID,
    ) -> Optional[TaskDB]:
        """Sync task status from Clawith.
        
        Args:
            task_id: Local task ID
            
        Returns:
            Updated TaskDB if successful
        """
        if not self.clawith:
            logger.warning("Clawith client not configured")
            return None
        
        # Get task
        task = self.db.query(TaskDB).filter(TaskDB.id == task_id).first()
        
        if not task:
            logger.warning(f"Task {task_id} not found")
            return None
        
        if not task.clawith_task_id:
            logger.warning(f"Task {task_id} has no Clawith ID")
            return task
        
        try:
            # Get status from Clawith
            status_data = await self.clawith.get_task_status(task.clawith_task_id)
            
            # Update local record
            old_status = task.status
            task.status = status_data.get("status", task.status)
            
            if task.status == "running" and old_status != "running":
                task.started_at = datetime.utcnow()
            
            if task.status in ("completed", "failed"):
                task.completed_at = datetime.utcnow()
            
            task.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.debug(f"Synced task {task_id} status: {task.status}")
            
            return task
            
        except Exception as e:
            logger.error(f"Failed to sync task from Clawith: {e}")
            self.db.rollback()
            raise
    
    async def sync_outputs_from_clawith(
        self,
        agent_id: UUID,
        company_id: UUID,
    ) -> int:
        """Sync agent outputs from Clawith.
        
        Args:
            agent_id: Local agent ID
            company_id: Company ID
            
        Returns:
            Number of new outputs synced
        """
        if not self.clawith:
            logger.warning("Clawith client not configured")
            return 0
        
        # Get agent
        agent = self.db.query(AgentDB).filter(
            AgentDB.id == agent_id,
            AgentDB.company_id == company_id,
        ).first()
        
        if not agent:
            logger.warning(f"Agent {agent_id} not found")
            return 0
        
        if not agent.clawith_agent_id:
            logger.warning(f"Agent {agent_id} has no Clawith ID")
            return 0
        
        # Get last sync time
        last_output = self.db.query(AgentOutputDB).filter(
            AgentOutputDB.agent_id == agent_id,
        ).order_by(AgentOutputDB.created_at.desc()).first()
        
        since = None
        if last_output:
            since = last_output.created_at.isoformat()
        
        try:
            # Get outputs from Clawith
            outputs = await self.clawith.get_agent_outputs(
                agent_id=agent.clawith_agent_id,
                since=since,
            )
            
            # Store new outputs
            count = 0
            for output_data in outputs:
                # Check if already exists
                existing = self.db.query(AgentOutputDB).filter(
                    AgentOutputDB.clawith_output_id == output_data.get("id"),
                ).first()
                
                if existing:
                    continue
                
                # Create new output
                output = AgentOutputDB(
                    company_id=company_id,
                    agent_id=agent_id,
                    task_id=None,  # Will be linked if task_id in metadata
                    output_type=output_data.get("type", "text"),
                    content=output_data.get("content", ""),
                    metadata=output_data.get("metadata", {}),
                    clawith_output_id=output_data.get("id"),
                )
                
                self.db.add(output)
                count += 1
            
            self.db.commit()
            
            if count > 0:
                logger.info(f"Synced {count} outputs for agent {agent_id}")
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to sync outputs from Clawith: {e}")
            self.db.rollback()
            raise
    
    async def sync_all_pending_tasks(
        self,
        company_id: Optional[UUID] = None,
    ) -> int:
        """Sync all pending tasks from Clawith.
        
        Args:
            company_id: Optional company ID filter
            
        Returns:
            Number of tasks synced
        """
        query = self.db.query(TaskDB).filter(
            TaskDB.status.in_(["pending", "running"]),
            TaskDB.clawith_task_id.isnot(None),
        )
        
        if company_id:
            query = query.filter(TaskDB.company_id == company_id)
        
        tasks = query.all()
        
        count = 0
        for task in tasks:
            try:
                await self.sync_task_from_clawith(task.id)
                count += 1
            except Exception as e:
                logger.error(f"Failed to sync task {task.id}: {e}")
        
        return count
