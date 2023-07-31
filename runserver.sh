#!/bin/bash
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export FLASK_APP="dashlive.server.app"

if [ ! -z "${VIRTUAL_ENV}" ]; then
    source ${VIRTUAL_ENV}/bin/activate
fi

if [ "${UID}" != "0" ]; then
    # no need to run lesscpy when running inside a Docker
    # container because that was done during the build
    # process
    python -m lesscpy static/css -o static/css/
fi

PYTHONPATH=${PWD} flask run --host=0.0.0.0 --debug
