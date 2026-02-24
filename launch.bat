@echo off
title OTC Options Calculator
cd /d "C:\Users\gfiglesias\appOTCoptionsCALCULATOR"

echo Instalando dependencias...
pip install -r requirements.txt >nul 2>&1

echo Iniciando servidor Flask...
start "" http://localhost:5000
python app.py
