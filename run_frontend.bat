@echo off
REM Start the Streamlit dashboard (Windows). Backend must already be running.
python -m streamlit run frontend/app.py --server.port 8501
