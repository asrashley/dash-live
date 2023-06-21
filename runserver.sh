#!/bin/bash
python -m lesscpy static/css -o static/css/
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export FLASK_APP="dashlive.server.app"

PYTHONPATH=${PWD} flask run --host=0.0.0.0 --debug
