@echo off
title AlphaRank Stock Dashboard
echo ===================================================
echo Starting AlphaRank Multi-Factor Stock Dashboard...
echo ===================================================
streamlit run app.py --server.port 8501 --server.headless true
pause
