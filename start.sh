#!/bin/bash
# Mann Made Socializer - Start script
# Starts the FastAPI server on port 7070

cd "$(dirname "$0")"
exec python3 -m uvicorn server:app --host 0.0.0.0 --port 7070
