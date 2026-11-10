#!/usr/bin/env bash
# Start the Streamlit dashboard (macOS / Linux). Backend must already be running.
python -m streamlit run frontend/app.py --server.port 8501
