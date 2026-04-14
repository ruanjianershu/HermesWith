#!/bin/bash
# Stop all HermesWith services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🛑 Stopping HermesWith services..."
docker-compose down

echo "✅ All services stopped"
