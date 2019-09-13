@echo off
SETLOCAL ENABLEEXTENSIONS
SET GAEDATA=%LOCALAPPDATA%\.gaedata
if not exist %GAEDATA% mkdir %GAEDATA%
dev_appserver.py --port=9080 --host=0.0.0.0 --admin_host=0.0.0.0 --admin_port=9081 --datastore_path=%GAEDATA%\datastore.sql3 --enable_host_checking False app.yaml
