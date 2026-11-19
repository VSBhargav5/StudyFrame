@echo off
setlocal
cd /d "%~dp0"
if exist "out\portable-v0.10.0\StudyFrame\StudyFrame.exe" (
  start "" "out\portable-v0.10.0\StudyFrame\StudyFrame.exe"
  exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
  echo StudyFrame's Python environment is missing. Follow Run on Windows in README.md first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m studyframe
if errorlevel 1 pause
