#!/bin/bash

function die() {
  echo $*
  exit 1
}

if [ -f /home/dash/.local/bin/env ]; then
    source /home/dash/.local/bin/env
fi

if [ "x${USER_UID}" != "x" -a "x${USER_GID}" != "x" ]; then
    echo "Using user UID ${USER_UID} and group GID ${USER_GID} for encoder user"
    addgroup --quiet --gid=${USER_GID} encoder
    adduser --quiet --system --uid ${USER_UID} --gid ${USER_GID}  --home /home/dash --no-create-home encoder
fi

cd ${HOME}/dash-live && exec runuser -u encoder -- uv run -m dashlive.media.create $*