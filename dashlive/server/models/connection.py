#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import json
from os import environ
from pathlib import Path
import re

from sqlalchemy import URL

def make_db_connection_string(instance_path: Path, url_template: str) -> str:
    """
    Create a connection URL containing all the database settings
    """
    def to_string(item: str | None) -> str:
        if item is None:
            return ''
        return item

    driver = environ.get("DB_DRIVER", None)
    engine = environ.get("DB_ENGINE", "sqlite")
    user = environ.get("DB_USER", None)
    password = environ.get("DB_PASS", None)
    port = environ.get("DB_PORT", None)
    host = environ.get("DB_HOST", None)
    db_name = environ.get("DB_NAME", "models.db3")
    connect_timeout = environ.get("DB_CONNECT_TIMEOUT", "")

    if engine == 'sqlite':
        abs_name = (instance_path / db_name).resolve()
        db_name = abs_name.as_posix()
    opts = {}
    if environ.get("DB_SSL"):
        ssl = json.loads(environ.get("DB_SSL", ""))
        opts['ssl'] = 'true'
        for key, value in ssl.items():
            if key == 'ssl_mode' or not value:
                continue
            opts[key] = value
    if connect_timeout:
        opts['connect_timeout'] = connect_timeout
    if driver:
        opts['driver'] = driver
    uri = URL.create(engine, username=user, password=password,
                     host=host, database=db_name, query=opts)
    url_tokens = {
        "DB_ENGINE": engine,
        "DB_USER": to_string(user),
        "DB_PASS": to_string(password),
        "DB_PORT": to_string(port),
        "DB_HOST": to_string(host),
        "DB_NAME": db_name,
        "DB_URI": uri.render_as_string(hide_password=False),
    }
    return re.sub(r"\${(.+?)}", lambda m: url_tokens[m.group(1)], url_template)
