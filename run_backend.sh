#!/usr/bin/env bash
# Start the FastAPI backend (macOS / Linux). Run from the project folder with the venv activated.
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
