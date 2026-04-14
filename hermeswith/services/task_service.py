"""Task service for managing tasks."""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from hermeswith.integrations.clawith_client import ClawithClient
from hermeswith.integrations.sync_service import SyncService
from hermeswith.persistence.models import AgentDB, TaskDB

logger = logging.getLogger(__name__)


class TaskService:
    """Service for task management."""
    
    def __init__(
        self,
        db: Session,
        clawith_client: Optional[ClawithClient] = None,
    ):
        """Initialize task service.
        
        Args:
            db: Database session
            clawith_client: Optional Clawith client for sync
        """
        self.db = db
        self.clawith = clawith_client
        self.sync_service = SyncService(db, clawith_client) if clawith_client else None
    
    def create_task(
        self,
        company_id: UUID,
        agent_id: UUID,
        title: str,
        instruction: str,
        description: Optional[str] = None,
        priority: str = "medium",
    ) -> Optional[TaskDB]:
        """Create a new task.
        
        Args:
            company_id: Company ID
            agent_id: Agent ID
            title: Task title
            instruction: Task instruction
            description: Optional description
            priority: Task priority (low, medium, high, urgent)
            
        Returns:
            Created TaskDB if agent exists, None otherwise
        """
        # Verify agent exists and belongs to company
        agent = self.db.query(AgentDB).filter(
            AgentDB.id == agent_id,
            AgentDB.company_id == company_id,
            AgentDB.is_active == True,
        ).first()
        
        if not agent:
            logger.warning(f"Agent {agent_id} not found for company {company_id}")
            return None
        
        task = TaskDB(
            company_id=company_id,
            agent_id=agent_id,
            title=title,
            description=description,
            instruction=instruction,
            status="created",
            priority=priority,
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        logger.info(f"Created task {task.id} for agent {agent_id}")
        
        return task
    
    def get_task(
        self,
        company_id: UUID,
        task_id: UUID,
    ) -> Optional[TaskDB]:
        """Get a task by ID.
        
        Args:
            company_id: Company ID
            task_id: Task ID
            
        Returns:
            TaskDB if found, None otherwise
        """
        return self.db.query(TaskDB).filter(
            TaskDB.id == task_id,
            TaskDB.company_id == company_id,
        ).first()
    
    def list_tasks(
        self,
        company_id: UUID,
        agent_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[TaskDB]:
        """List tasks for a company.
        
        Args:
            company_id: Company ID
            agent_id: Optional agent ID filter
            status: Optional status filter
            
        Returns:
            List of TaskDB instances
        """
        query = self.db.query(TaskDB).filter(
            TaskDB.company_id == company_id,
        )
        
        if agent_id:
            query = query.filter(TaskDB.agent_id == agent_id)
        
        if status:
            query = query.filter(TaskDB.status == status)
        
        return query.order_by(TaskDB.created_at.desc()).all()
    
    def assign_task_to_agent(
        self,
        company_id: UUID,
        task_id: UUID,
    ) -> bool:
        """Assign task to agent (sync with Clawith).
        
        Args:
            company_id: Company ID
            task_id: Task ID
            
        Returns:
            True if assigned successfully
        """
        task = self.get_task(company_id, task_id)
        
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False
        
        if not self.sync_service:
            logger.warning("Sync service not available")
            # Just mark as pending without Clawith
            task.status = "pending"
            self.db.commit()
            return True
        
        try:
            import asyncio
            # Run sync synchronously for this operation
            clawith_task_id = asyncio.run(
                self.sync_service.sync_task_to_clawith(task)
            )
            
            if clawith_task_id:
                logger.info(f"Task {task_id} assigned to Clawith: {clawith_task_id}")
                return True
            else:
                logger.error(f"Failed to sync task {task_id} to Clawith")
                return False
                
        except Exception as e:
            logger.error(f"Error assigning task {task_id}: {e}")
            return False
    
    def sync_task_status(
        self,
        company_id: UUID,
        task_id: UUID,
    ) -> Optional[TaskDB]:
        """Sync task status from Clawith.
        
        Args:
            company_id: Company ID
            task_id: Task ID
            
        Returns:
            Updated TaskDB if successful
        """
        if not self.sync_service:
            return None
        
        try:
            import asyncio
            return asyncio.run(
                self.sync_service.sync_task_from_clawith(task_id)
            )
        except Exception as e:
            logger.error(f"Error syncing task {task_id}: {e}")
            return None
    
    def cancel_task(
        self,
        company_id: UUID,
        task_id: UUID,
    ) -> bool:
        """Cancel a task.
        
        Args:
            company_id: Company ID
            task_id: Task ID
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        task = self.get_task(company_id, task_id)
        
        if not task:
            return False
        
        if task.status in ("completed", "failed", "cancelled"):
            logger.warning(f"Cannot cancel task {task_id} with status {task.status}")
            return False
        
        task.status = "cancelled"
        self.db.commit()
        
        logger.info(f"Cancelled task {task_id}")
        
        return True
    
    def get_task_outputs(
        self,
        company_id: UUID,
        task_id: UUID,
    ) -> List:
        """Get outputs for a task.
        
        Args:
            company_id: Company ID
            task_id: Task ID
            
        Returns:
            List of AgentOutputDB instances
        """
        from hermeswith.persistence.models import AgentOutputDB
        
        return self.db.query(AgentOutputDB).filter(
            AgentOutputDB.task_id == task_id,
            AgentOutputDB.company_id == company_id,
        ).order_by(AgentOutputDB.created_at.desc()).all()
