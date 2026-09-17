@echo off
title pieczapp
cd /d "%~dp0"
if not exist .venv (
  echo Pierwsze uruchomienie - tworze srodowisko...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
  pip install -q -r requirements.txt
)
set AWS_REGION=eu-central-1
start "" http://127.0.0.1:8000
python app.py
