$Env:LC_ALL = "C.UTF-8"
$Env:LANG = "C.UTF-8"
$Env:FLASK_APP = "dashlive.server.app"

npm run legacy-css
npm run main-css
python -m flask --app dashlive.server.app run --host=0.0.0.0 --debug
