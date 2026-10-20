#!/bin/bash
cd "$(dirname "$0")"
exec python3 -m uvicorn server.main:app --app-dir backend --host 0.0.0.0 --port 8000
