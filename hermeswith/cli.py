"""CLI tool for Hermeswith management."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

import typer
from sqlalchemy.orm import Session

from hermeswith.config import settings
from hermeswith.persistence.database import get_db, init_db
from hermeswith.persistence.models import APIKeyDB, CompanyDB
from hermeswith.security.auth import hash_api_key

app = typer.Typer(help="Hermeswith CLI")


def get_db_session() -> Session:
    """Get database session."""
    return next(get_db())


@app.command()
def init_db_command():
    """Initialize the database."""
    typer.echo("Initializing database...")
    init_db()
    typer.echo("✓ Database initialized successfully")


@app.command()
def create_company(
    name: str = typer.Argument(..., help="Company name"),
    metadata_json: Optional[str] = typer.Option(None, "--metadata", "-m", help="JSON metadata"),
):
    """Create a new company."""
    import json
    
    db = get_db_session()
    
    metadata = {}
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            typer.echo("Error: Invalid JSON metadata", err=True)
            raise typer.Exit(1)
    
    company = CompanyDB(
        name=name,
        metadata=metadata,
        is_active=True,
    )
    
    db.add(company)
    db.commit()
    db.refresh(company)
    
    typer.echo(f"✓ Created company: {company.name}")
    typer.echo(f"  ID: {company.id}")


@app.command()
def create_api_key(
    company_id: str = typer.Argument(..., help="Company UUID"),
    name: str = typer.Option("Default", "--name", "-n", help="Key name"),
    permissions: str = typer.Option("read,write", "--permissions", "-p", help="Comma-separated permissions"),
    expires_days: int = typer.Option(365, "--expires", "-e", help="Days until expiration"),
):
    """Create a new API key for a company."""
    from uuid import UUID
    
    db = get_db_session()
    
    # Verify company exists
    try:
        company_uuid = UUID(company_id)
    except ValueError:
        typer.echo("Error: Invalid company ID format", err=True)
        raise typer.Exit(1)
    
    company = db.query(CompanyDB).filter(CompanyDB.id == company_uuid).first()
    if not company:
        typer.echo("Error: Company not found", err=True)
        raise typer.Exit(1)
    
    # Generate API key
    api_key = f"hw_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(api_key)
    
    # Parse permissions
    perms = [p.strip() for p in permissions.split(",")]
    
    # Create API key record
    api_key_record = APIKeyDB(
        company_id=company_uuid,
        name=name,
        key_hash=key_hash,
        permissions=perms,
        expires_at=datetime.utcnow() + timedelta(days=expires_days),
        is_active=True,
    )
    
    db.add(api_key_record)
    db.commit()
    
    typer.echo(f"✓ Created API key for company: {company.name}")
    typer.echo(f"  Name: {name}")
    typer.echo(f"  Permissions: {', '.join(perms)}")
    typer.echo(f"  Expires: {api_key_record.expires_at.date()}")
    typer.echo("")
    typer.echo(f"  API Key: {api_key}")
    typer.echo("")
    typer.echo("  ⚠️  Save this key now - it won't be shown again!")


@app.command()
def list_companies():
    """List all companies."""
    db = get_db_session()
    
    companies = db.query(CompanyDB).all()
    
    if not companies:
        typer.echo("No companies found")
        return
    
    typer.echo(f"{'ID':<36} {'Name':<30} {'Active':<8} {'Created'}")
    typer.echo("-" * 100)
    
    for company in companies:
        typer.echo(
            f"{str(company.id):<36} "
            f"{company.name:<30} "
            f"{'Yes' if company.is_active else 'No':<8} "
            f"{company.created_at.date()}"
        )


@app.command()
def list_api_keys(
    company_id: Optional[str] = typer.Option(None, "--company", "-c", help="Filter by company ID"),
):
    """List API keys."""
    from uuid import UUID
    
    db = get_db_session()
    
    query = db.query(APIKeyDB)
    
    if company_id:
        try:
            query = query.filter(APIKeyDB.company_id == UUID(company_id))
        except ValueError:
            typer.echo("Error: Invalid company ID format", err=True)
            raise typer.Exit(1)
    
    keys = query.all()
    
    if not keys:
        typer.echo("No API keys found")
        return
    
    typer.echo(f"{'Name':<20} {'Company':<30} {'Permissions':<20} {'Active':<8} {'Expires'}")
    typer.echo("-" * 100)
    
    for key in keys:
        company = db.query(CompanyDB).filter(CompanyDB.id == key.company_id).first()
        company_name = company.name if company else "Unknown"
        perms = ",".join(key.permissions or [])
        
        typer.echo(
            f"{key.name:<20} "
            f"{company_name:<30} "
            f"{perms:<20} "
            f"{'Yes' if key.is_active else 'No':<8} "
            f"{key.expires_at.date()}"
        )


@app.command()
def server(
    host: str = typer.Option(settings.HOST, "--host", "-h", help="Host to bind"),
    port: int = typer.Option(settings.PORT, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the API server."""
    import uvicorn
    
    typer.echo(f"Starting Hermeswith API server on {host}:{port}")
    
    uvicorn.run(
        "hermeswith.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    app()
