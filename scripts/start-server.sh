#!/bin/bash
# Start HoneyAgent API server

set -e

echo "🍯 Starting HoneyAgent API..."
echo ""

# Activate venv
source .venv/bin/activate

# Export PYTHONPATH
export PYTHONPATH=/Users/ariaxhan/Documents/Vaults/CodingVault/hackathons/contextlake/aws-aoh-hackathon:$PYTHONPATH

# Start server
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
