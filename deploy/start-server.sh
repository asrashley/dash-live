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

if [ -f /home/dash/instance/models.db3 ]; then
    if [ -f /home/dash/instance/.NEWDB ]; then
        # if the DB was created last time the server was started,
        # tell Alembic that the DB is upto date
        python -m alembic stamp head && rm /home/dash/instance/.NEWDB
    else
        python -m alembic upgrade head
    fi
else
    touch /home/dash/instance/.NEWDB
fi

GUNICORN_OPTIONS="-w 1 --threads 100 --user www-data --group www-data --worker-class gthread"

echo Starting server with Origin ${SERVER_NAME}:${SERVER_PORT}

if [ -f /etc/nginx/sites-available/dashlive.conf ]; then
    gunicorn ${GUNICORN_OPTIONS} -b 127.0.0.1:5000 --daemon application:app
    nginx -g "daemon off;"
else
    gunicorn ${GUNICORN_OPTIONS} -b 127.0.0.1:80 application:app
fi


