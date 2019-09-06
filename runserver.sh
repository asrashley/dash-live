#!/bin/sh
if [ -z "${GAEDATA}" ]; then
    export GAEDATA="${HOME}/.gaedata"
fi
if [ ! -d ${GAEDATA} ]; then
  mkdir ${GAEDATA}
fi
exec dev_appserver.py --port=9080 --host=0.0.0.0  --admin_host=0.0.0.0 --admin_port=9081 --storage_path=${GAEDATA} --dev_appserver_log_level=info app.yaml 
