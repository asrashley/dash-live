#!/bin/bash

if [ -d /home/dash/.venv ]; then
    rm -rf /home/dash/.venv
fi
python3 -m venv /home/dash/.venv
source /home/dash/.venv/bin/activate
pip3 install --prefix /home/dash/.venv -r /home/dash/dash-live/requirements.txt
pip3 install gunicorn==21.2.0
