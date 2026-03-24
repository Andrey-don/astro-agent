@echo off
cd /d "C:\Users\profi\Documents\Project\astro-agent"
start "" "http://localhost:5000"
python -m web.app
