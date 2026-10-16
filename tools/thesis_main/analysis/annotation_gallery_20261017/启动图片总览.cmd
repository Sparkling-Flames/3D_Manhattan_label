@echo off
cd /d "%~dp0..\..\..\.."
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Start-Process -FilePath (Get-Command python).Source -ArgumentList '-m','tools.thesis_main.analysis.annotation_gallery_server_20261017','--open-browser' -WorkingDirectory (Get-Location).Path -WindowStyle Hidden"
if errorlevel 1 pause
