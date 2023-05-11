#!/bin/bash
if [ -z "${GAEDATA}" ]; then
    export GAEDATA="${HOME}/.gaedata"
fi
if [ ! -d ${GAEDATA} ]; then
  mkdir ${GAEDATA}
fi
if [ -z "${PORT}" ]; then
    PORT=9080
fi
if [ -z "${LOG_LEVEL}" ]; then
    LOG_LEVEL="info"
fi
let ADMIN_PORT=$(( $PORT + 1))
HOST_CHECKING=""
if dev_appserver.py -h | grep -q enable_host_checking ; then
  HOST_CHECKING="--enable_host_checking False"
fi
python -m lesscpy static/css -o static/css/
exec dev_appserver.py --port=${PORT} --host=0.0.0.0  --admin_host=0.0.0.0 --admin_port=${ADMIN_PORT} --storage_path=${GAEDATA} --dev_appserver_log_level=${LOG_LEVEL} ${HOST_CHECKING} app.yaml
