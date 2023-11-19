#!/bin/bash

source /home/dash/.venv/bin/activate
source /home/dash/dash-live/.env

cd /home/dash/dash-live

pip3 install --prefix /home/dash/.venv -r /home/dash/dash-live/dev-requirements.txt

pytest -n auto
