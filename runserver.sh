#!/bin/bash
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export FLASK_APP="dashlive.server.app"

if [ ! -z "${VIRTUAL_ENV}" ]; then
    source ${VIRTUAL_ENV}/bin/activate
fi

PYTHONPATH=${PWD} flask run --host=0.0.0.0 --debug
