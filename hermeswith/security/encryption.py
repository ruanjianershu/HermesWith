"""Encryption module for HermesWith - Fernet symmetric encryption for sensitive data."""

import os
import base64
import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeswith.persistence.database import AsyncSessionLocal
from hermeswith.persistence.models import EncryptedConfigDB


class EncryptionManager:
    """
    Manages Fernet symmetric encryption for sensitive configuration data.
    Supports key rotation with versioning.
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize the encryption manager.
        
        Args:
            master_key: Base64-encoded Fernet key. If not provided, loads from env.
        """
        self._keys: Dict[str, Fernet] = {}  # version -> Fernet instance
        self._current_version: str = "v1"
        
        # Load master key from environment or parameter
        if master_key:
            self._master_key = master_key.encode() if isinstance(master_key, str) else master_key
        else:
            env_key = os.getenv("HERMESWITH_ENCRYPTION_KEY")
            if env_key:
                self._master_key = env_key.encode()
            else:
                # Generate a new key (only for development!)
                self._master_key = Fernet.generate_key()
                print("⚠️  WARNING: Generated temporary encryption key. Set HERMESWITH_ENCRYPTION_KEY in production!")
        
        # Initialize with current key
        self._add_key(self._current_version, self._master_key)
    
    def _add_key(self, version: str, key: bytes):
        """Add a key version for decryption (supports rotation)."""
        # Ensure key is valid Fernet key
        if isinstance(key, str):
            key = key.encode()
        
        try:
            fernet = Fernet(key)
            self._keys[version] = fernet
        except Exception as e:
            raise ValueError(f"Invalid encryption key for version {version}: {e}")
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet key."""
        return Fernet.generate_key().decode()
    
    def encrypt(self, plaintext: str, version: Optional[str] = None) -> Dict[str, str]:
        """
        Encrypt plaintext data.
        
        Returns:
            Dict with 'encrypted_value' and 'key_version'
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty value")
        
        ver = version or self._current_version
        fernet = self._keys.get(ver)
        
        if not fernet:
            raise ValueError(f"Unknown key version: {ver}")
        
        encrypted = fernet.encrypt(plaintext.encode())
        
        return {
            "encrypted_value": base64.b64encode(encrypted).decode(),
            "key_version": ver,
        }
    
    def decrypt(self, encrypted_value: str, version: str) -> str:
        """
        Decrypt encrypted data.
        
        Args:
            encrypted_value: Base64-encoded encrypted string
            version: Key version used for encryption
        
        Returns:
            Decrypted plaintext
        """
        fernet = self._keys.get(version)
        
        if not fernet:
            raise ValueError(f"Unknown key version: {version}. Cannot decrypt.")
        
        try:
            encrypted_bytes = base64.b64decode(encrypted_value.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except InvalidToken:
            raise ValueError("Invalid or corrupted encrypted value")
    
    def rotate_key(self, new_key: Optional[str] = None) -> str:
        """
        Rotate to a new encryption key.
        
        Args:
            new_key: New Fernet key. If not provided, generates one.
        
        Returns:
            New version identifier
        """
        if new_key is None:
            new_key = Fernet.generate_key().decode()
        
        # Generate new version based on timestamp
        new_version = f"v{int(datetime.utcnow().timestamp())}"
        
        self._add_key(new_version, new_key.encode() if isinstance(new_key, str) else new_key)
        self._current_version = new_version
        
        return new_version
    
    async def store_encrypted_config(
        self,
        company_id: str,
        config_type: str,
        config_key: str,
        value: str,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Store an encrypted configuration value.
        
        Args:
            company_id: Company UUID
            config_type: Type of config (e.g., 'api_key', 'secret')
            config_key: Unique key for this config
            value: Plaintext value to encrypt
            session: Optional database session
        
        Returns:
            Dict with config metadata
        """
        encrypted = self.encrypt(value)
        
        close_session = session is None
        if session is None:
            session = AsyncSessionLocal()
        
        try:
            import uuid
            
            # Check if config already exists
            result = await session.execute(
                select(EncryptedConfigDB).where(
                    EncryptedConfigDB.company_id == uuid.UUID(company_id),
                    EncryptedConfigDB.config_type == config_type,
                    EncryptedConfigDB.config_key == config_key
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing
                existing.encrypted_value = encrypted["encrypted_value"]
                existing.key_version = encrypted["key_version"]
                existing.updated_at = datetime.utcnow()
            else:
                # Create new
                config = EncryptedConfigDB(
                    id=uuid.uuid4(),
                    company_id=uuid.UUID(company_id),
                    config_type=config_type,
                    config_key=config_key,
                    encrypted_value=encrypted["encrypted_value"],
                    key_version=encrypted["key_version"],
                )
                session.add(config)
            
            await session.commit()
            
            return {
                "company_id": company_id,
                "config_type": config_type,
                "config_key": config_key,
                "key_version": encrypted["key_version"],
                "created_at": datetime.utcnow().isoformat(),
            }
        finally:
            if close_session:
                await session.close()
    
    async def get_encrypted_config(
        self,
        company_id: str,
        config_type: str,
        config_key: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[str]:
        """
        Retrieve and decrypt a configuration value.
        
        Returns:
            Decrypted plaintext value or None if not found
        """
        close_session = session is None
        if session is None:
            session = AsyncSessionLocal()
        
        try:
            import uuid
            
            result = await session.execute(
                select(EncryptedConfigDB).where(
                    EncryptedConfigDB.company_id == uuid.UUID(company_id),
                    EncryptedConfigDB.config_type == config_type,
                    EncryptedConfigDB.config_key == config_key
                )
            )
            config = result.scalar_one_or_none()
            
            if not config:
                return None
            
            return self.decrypt(config.encrypted_value, config.key_version)
        finally:
            if close_session:
                await session.close()
    
    async def delete_encrypted_config(
        self,
        company_id: str,
        config_type: str,
        config_key: str,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """Delete an encrypted configuration."""
        close_session = session is None
        if session is None:
            session = AsyncSessionLocal()
        
        try:
            import uuid
            
            result = await session.execute(
                select(EncryptedConfigDB).where(
                    EncryptedConfigDB.company_id == uuid.UUID(company_id),
                    EncryptedConfigDB.config_type == config_type,
                    EncryptedConfigDB.config_key == config_key
                )
            )
            config = result.scalar_one_or_none()
            
            if config:
                await session.delete(config)
                await session.commit()
                return True
            return False
        finally:
            if close_session:
                await session.close()
    
    async def list_encrypted_configs(
        self,
        company_id: str,
        config_type: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> List[Dict[str, Any]]:
        """List all encrypted configs for a company (without decrypted values)."""
        close_session = session is None
        if session is None:
            session = AsyncSessionLocal()
        
        try:
            import uuid
            
            stmt = select(EncryptedConfigDB).where(
                EncryptedConfigDB.company_id == uuid.UUID(company_id)
            )
            
            if config_type:
                stmt = stmt.where(EncryptedConfigDB.config_type == config_type)
            
            result = await session.execute(stmt)
            configs = result.scalars().all()
            
            return [
                {
                    "config_type": c.config_type,
                    "config_key": c.config_key,
                    "key_version": c.key_version,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in configs
            ]
        finally:
            if close_session:
                await session.close()


# Global encryption manager instance
_encryption_manager: Optional[EncryptionManager] = None


def get_encryption_manager() -> EncryptionManager:
    """Get or create the global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


def init_encryption_manager(master_key: Optional[str] = None) -> EncryptionManager:
    """Initialize the global encryption manager with a specific key."""
    global _encryption_manager
    _encryption_manager = EncryptionManager(master_key)
    return _encryption_manager
