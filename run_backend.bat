@echo off
REM Start the FastAPI backend (Windows). Run from the project folder with the venv activated.
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
