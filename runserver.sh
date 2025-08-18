#!/bin/bash
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export FLASK_APP="dashlive.server.app"
export SERVER_NAME=$(hostname -f)
export SERVER_PORT="5000"

if [ ! -z "${VIRTUAL_ENV}" ]; then
    source ${VIRTUAL_ENV}/bin/activate
fi

if [ "${UID}" != "0" ]; then
    # no need to run CSS building when running inside a Docker
    # container because that was done during the build
    # process
    npm run all-css
fi

PYTHONPATH=${PWD} flask run --host=0.0.0.0 --debug
