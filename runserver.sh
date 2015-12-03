#!/bin/sh
if [ ! -d .gaedata ]; then
  mkdir .gaedata
fi
#dev_appserver.py --port=9080 --host=0.0.0.0 --storage_path=.gaedata --dev_appserver_log_level=debug app.yaml 
exec dev_appserver.py --port=9080 --host=0.0.0.0 --storage_path=.gaedata --dev_appserver_log_level=info app.yaml 
