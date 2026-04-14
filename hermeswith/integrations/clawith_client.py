"""Clawith API client for agent and task management."""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ClawithError(Exception):
    """Base exception for Clawith API errors."""
    pass


class ClawithAuthError(ClawithError):
    """Authentication error."""
    pass


class ClawithNotFoundError(ClawithError):
    """Resource not found error."""
    pass


class ClawithRateLimitError(ClawithError):
    """Rate limit exceeded error."""
    pass


class ClawithClient:
    """Client for Clawith API."""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        """Initialize Clawith client.
        
        Args:
            base_url: Clawith API base URL
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and raise appropriate exceptions."""
        if response.status_code == 401:
            raise ClawithAuthError("Invalid API key")
        elif response.status_code == 403:
            raise ClawithAuthError("Permission denied")
        elif response.status_code == 404:
            raise ClawithNotFoundError("Resource not found")
        elif response.status_code == 429:
            raise ClawithRateLimitError("Rate limit exceeded")
        elif response.status_code >= 500:
            raise ClawithError(f"Server error: {response.status_code}")
        
        response.raise_for_status()
        
        if response.content:
            return response.json()
        return {}
    
    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def create_agent(
        self,
        name: str,
        model: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[str]] = None,
        company_id: Optional[UUID] = None,
    ) -> str:
        """Create an agent in Clawith.
        
        Args:
            name: Agent name
            model: Model identifier (e.g., "anthropic/claude-opus-4")
            system_prompt: System prompt for the agent
            tools: List of tool names to enable
            company_id: Company ID for tenant isolation
            
        Returns:
            str: Clawith agent ID
        """
        url = f"{self.base_url}/api/v1/agents"
        
        payload = {
            "name": name,
            "model": model,
            "system_prompt": system_prompt or "",
            "tools": tools or [],
        }
        
        if company_id:
            payload["metadata"] = {"company_id": str(company_id)}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=payload,
            )
            
            result = self._handle_response(response)
            return result.get("id")
    
    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def assign_task(
        self,
        agent_id: str,
        task_data: Dict[str, Any],
    ) -> str:
        """Assign a task to an agent.
        
        Args:
            agent_id: Clawith agent ID
            task_data: Task data including title, description, instruction
            
        Returns:
            str: Clawith task ID
        """
        url = f"{self.base_url}/api/v1/agents/{agent_id}/tasks"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=task_data,
            )
            
            result = self._handle_response(response)
            return result.get("id")
    
    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def get_task_status(
        self,
        task_id: str,
    ) -> Dict[str, Any]:
        """Get task status.
        
        Args:
            task_id: Clawith task ID
            
        Returns:
            Dict with status, result, error, etc.
        """
        url = f"{self.base_url}/api/v1/tasks/{task_id}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers)
            return self._handle_response(response)
    
    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def get_task_output(
        self,
        task_id: str,
    ) -> Dict[str, Any]:
        """Get task output.
        
        Args:
            task_id: Clawith task ID
            
        Returns:
            Dict with output content, type, metadata
        """
        url = f"{self.base_url}/api/v1/tasks/{task_id}/output"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers)
            return self._handle_response(response)
    
    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def list_agents(
        self,
        company_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """List agents.
        
        Args:
            company_id: Filter by company ID
            
        Returns:
            List of agent data
        """
        url = f"{self.base_url}/api/v1/agents"
        params = {}
        
        if company_id:
            params["company_id"] = str(company_id)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers, params=params)
            result = self._handle_response(response)
            return result.get("agents", [])
    
    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def delete_agent(
        self,
        agent_id: str,
    ) -> bool:
        """Delete an agent.
        
        Args:
            agent_id: Clawith agent ID
            
        Returns:
            True if successful
        """
        url = f"{self.base_url}/api/v1/agents/{agent_id}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(url, headers=self.headers)
            
            if response.status_code == 404:
                return False
            
            self._handle_response(response)
            return True
    
    @retry(
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def get_agent_outputs(
        self,
        agent_id: str,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get agent outputs.
        
        Args:
            agent_id: Clawith agent ID
            since: ISO timestamp to filter outputs
            
        Returns:
            List of output data
        """
        url = f"{self.base_url}/api/v1/agents/{agent_id}/outputs"
        params = {}
        
        if since:
            params["since"] = since
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers, params=params)
            result = self._handle_response(response)
            return result.get("outputs", [])
