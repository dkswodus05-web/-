@echo off
chcp 65001 >nul
set PYTHONUTF8=1
REM Windows 작업 스케줄러가 이 파일 하나만 실행하면 됩니다.
REM Claude 앱이 꺼져 있어도 동작합니다. 실행 결과는 trades.log / pipeline_stdout.log에 남습니다.
cd /d "%~dp0"
python daily_pipeline.py >> pipeline_stdout.log 2>&1
