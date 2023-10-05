#!/bin/bash
source /home/dash/.venv/bin/activate

if [ -z "${SERVER_NAME}" ]; then
    echo "Using server name ${SERVER_NAME}"
    SERVER_NAME="_"
fi

if [ "x${USER_UID}" != "x" -a "x${USER_GID}" != "x" ]; then
    echo "Using user UID ${USER_UID} and group GID ${USER_GID} for www-data user"
    deluser www-data
    delgroup www-data
    addgroup --gid=${USER_GID} www-data
    adduser --system --uid ${USER_UID} --gid ${USER_GID} --no-create-home www-data
    # usermod -g ${USER_GID} www-data
fi
echo "server_name ${SERVER_NAME};" > /etc/nginx/snippets/server_name.conf

python -m alembic upgrade head

if [ -f /etc/uwsgi/sites/dash.ini ]; then
    mkdir /run/uwsgi
    chown www-data:www-data /run/uwsgi
    uwsgi --ini /etc/uwsgi/sites/dash.ini &
    nginx -g "daemon off;"
else
    uwsgi --uid www-data --gid www-data --http localhost:80 --gevent 100 --http-websockets --module application:app
fi


