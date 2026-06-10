@echo off
rem Daily trendwatch snapshot (registered in Task Scheduler as "refcap-trendwatch").
rem Deterministic, model-free: fetch keyed Data API stats for the watchlist, append to the ledger.
cd /d "%~dp0"
python trendwatch.py snapshot >> "%~dp0research\trendwatch\task.log" 2>&1
