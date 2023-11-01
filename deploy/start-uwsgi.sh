#!/bin/bash

source /home/dash/.venv/bin/activate
source /home/dash/dash-live/.env

if [ -z "${SERVER_NAME}" ]; then
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

cd /home/dash/dash-live

python -m alembic upgrade head

GUNICORN_OPTIONS="-w 1 --threads 100 --user www-data --group www-data --worker-class gthread"

if [ -f /etc/uwsgi/sites/dash.ini ]; then
    gunicorn ${GUNICORN_OPTIONS} -b 127.0.0.1:5000 --daemon application:app
    nginx -g "daemon off;"
else
    gunicorn ${GUNICORN_OPTIONS} -b 127.0.0.1:80 application:app
fi


