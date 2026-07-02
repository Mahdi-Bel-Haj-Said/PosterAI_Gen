@echo off
REM Double-click this to launch the whole EsportsPostAI stack
REM (Docker -> Redis + Mongo -> API -> worker -> frontend -> browser).
title EsportsPostAI launcher
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all.ps1"
