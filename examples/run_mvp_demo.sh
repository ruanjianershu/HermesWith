#!/bin/bash
# Run the HermesWith MVP Demo

set -e

cd "$(dirname "$0")/.."

echo "🧪 Running HermesWith MVP Demo..."
python examples/mvp_demo.py
