@echo off
rem python "c:\Program Files (x86)\Google\google_appengine\dev_appserver.py" --port=9080 --host=0.0.0.0 --datastore_path=.gaedata\datastore.sql3 --clear_datastore true app.yaml 
dev_appserver.py --port=9080 --host=0.0.0.0 --datastore_path=.gaedata\datastore.sql3 app.yaml
rem python "..\google_appengine\dev_appserver.py" --port=9080 --host=0.0.0.0 --datastore_path=.gaedata\datastore.sql3 app.yaml 