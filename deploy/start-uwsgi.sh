#!/bin/bash
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

if [ -f /etc/uwsgi/sites/dash.ini ]; then
    mkdir /run/uwsgi
    chown www-data:www-data /run/uwsgi
    uwsgi --uid www-data --gid www-data --ini /etc/uwsgi/sites/dash.ini &
    nginx -g "daemon off;"
else
    uwsgi --http localhost:80 --module application:app --enable-threads --uid www-data --gid www-data
fi


