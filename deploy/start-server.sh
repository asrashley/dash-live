#!/bin/bash

function die() {
  echo $*
  exit 1
}

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

DB_FILE="/home/dash/instance/models.db3"

if [ ! -f ${DB_FILE} ]; then
    echo "No sqlite database found, creating a new one"
    python -m dashlive.management.create_db || die "Failed to create database"
    # tell Alembic that the DB is up to date
    python -m alembic stamp head
else
    python -m alembic upgrade head
fi

if [ ! -f ${DB_FILE} ]; then
    echo "Failed to create database ${DB_FILE}"
    exit 2
fi

chown www-data:www-data ${DB_FILE} || die "failed to set owner of ${DB_FILE} to ${USER_UID}:${USER_GID}"

echo Starting server with Origin ${SERVER_NAME}:${SERVER_PORT}

if [ -f /etc/nginx/sites-available/dashlive.conf -a -z "${DISABLE_NGINX}" ]; then
    gunicorn -c gunicorn.conf.py -b 127.0.0.1:5000 --daemon application:app
    nginx -g "daemon off;"
else
    gunicorn -c gunicorn.conf.py -b 0.0.0.0:80 application:app
fi


