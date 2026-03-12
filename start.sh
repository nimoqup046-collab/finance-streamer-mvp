#!/bin/bash
set -e
echo "Starting Finance Streamer Assistant..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
