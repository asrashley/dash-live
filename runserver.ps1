$Env:LC_ALL = "C.UTF-8"
$Env:LANG = "C.UTF-8"
$Env:FLASK_APP = "dashlive.server.app"
$Env:SERVER_NAME = $Env:COMPUTERNAME
$Env:SERVER_PORT = "5000"

npm run all-css
npm run build
uv run flask --app dashlive.server.app run --host=0.0.0.0 --debug
