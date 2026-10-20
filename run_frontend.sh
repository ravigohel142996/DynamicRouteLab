#!/bin/bash
cd "$(dirname "$0")/frontend"
exec npm run dev -- --host 0.0.0.0 --port 5173
