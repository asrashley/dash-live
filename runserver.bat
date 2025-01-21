@echo off
set LC_ALL=C.UTF-8
set LANG=C.UTF-8
set FLASK_APP="dashlive.server.app"

python -m flask --app dashlive.server.app run --host=0.0.0.0 --debug
