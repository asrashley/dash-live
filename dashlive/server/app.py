#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import importlib
import logging
from logging.config import dictConfig
from os import environ
import mimetypes
import secrets

from dotenv import load_dotenv
from flask import Flask, request, Response  # type: ignore
from flask_login import LoginManager
from flask_socketio import SocketIO
from werkzeug.routing import BaseConverter, Map  # type: ignore
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_jwt_extended import JWTManager

from dashlive.server import models
from dashlive.server.models.connection import make_db_connection_string
from dashlive.server.requesthandler.websocket import WebsocketHandler
from dashlive.utils.json_object import JsonObject

from .anonymous_user import AnonymousUser
from .asyncio_loop import asyncio_loop
from .folders import AppFolders
from .routes import routes
from .template_tags import custom_tags
# from .thread_pool import pool_executor

login_manager = LoginManager()

class RegexConverter(BaseConverter):
    """
    Utility class to allow a regex to be used in a route path
    """
    def __init__(self, url_map: Map, *items) -> None:
        super().__init__(url_map)
        self.regex = items[0]

def no_api_cache(response: Response) -> Response:
    """
    Make sure all API calls return no caching directives
    """
    if (request.is_json or
            request.args.get('ajax', '0') == '1'):
        response.cache_control.max_age = 0
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
    return response

def add_routes(app: Flask) -> None:
    app.url_map.converters['regex'] = RegexConverter
    app.after_request(no_api_cache)
    for name, route in routes.items():
        full_path = f'dashlive.server.requesthandler.{route.handler}'
        pos = full_path.rindex('.')
        module_name = full_path[:pos]
        handler_name = full_path[pos + 1:]
        module = importlib.import_module(module_name)
        view = getattr(module, handler_name)
        try:
            view_func = view.as_view(name)
        except AttributeError:
            view_func = view
        app.add_url_rule(route.template, endpoint=name,
                         view_func=view_func)

def create_app(config: JsonObject | None = None,
               instance_path: str | None = None,
               create_default_user: bool = True,
               wss: bool = True) -> Flask:
    if config is None:
        load_dotenv(environ.get('DASHLIVE_SETTINGS', '.env'))
    logging.basicConfig()
    folders = AppFolders(instance_path)
    folders.check(check_media=False)
    folders.create_media_folders()
    folders.check(check_media=True)
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("images/x-icon", ".ico", strict=False)
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("application/javascript", ".mjs")
    asyncio_loop.start()
    app = Flask(
        __name__,
        instance_path=folders.instance_path,
        template_folder=str(folders.template_folder),
        static_folder=str(folders.static_folder))
    add_routes(app)
    dash_settings = {
        'CSRF_SECRET': secrets.token_urlsafe(16),
        'DEFAULT_ADMIN_USERNAME': 'admin',
        'DEFAULT_ADMIN_PASSWORD': secrets.token_urlsafe(10),
    }
    url_template = environ.get('FLASK_DATABSE_TEMPLATE', r'${DB_URI}')
    database_uri = environ.get(
        'SQLALCHEMY_DATABASE_URI',
        make_db_connection_string(folders.instance_path, url_template))
    app.config.update(
        BLOB_FOLDER=str(folders.blob_folder),
        SQLALCHEMY_DATABASE_URI=database_uri,
        STATIC_FOLDER=str(folders.static_folder),
        UPLOAD_FOLDER=str(folders.upload_folder),
        DASH=dash_settings,
        SECRET_KEY=secrets.token_urlsafe(16),
        SESSION_COOKIE_SAMESITE='Strict'
    )
    app.config.from_prefixed_env()

    dictConfig({
        'version': 1,
        'formatters': {
            'default': {
                'format': '%(asctime)s %(levelname)s:%(module)s: %(message)s',
            }
        },
        'handlers': {
            'wsgi': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://flask.logging.wsgi_errors_stream',
                'formatter': 'default'
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })

    if config is not None:
        app.config.update(config)
    log_level = app.config.get('LOG_LEVEL')
    if log_level:
        logging.getLogger().setLevel(log_level.upper())
    for module in ['fio', 'mp4']:
        log_level = app.config.get(f'{module.upper()}_LOG_LEVEL', 'warning')
        log = logging.getLogger(module)
        log.setLevel(log_level.upper())
    models.db.init_app(app)
    jwt = JWTManager(app)
    login_manager.anonymous_user = AnonymousUser
    login_manager.init_app(app)

    # pylint: disable=unused-variable
    @jwt.user_lookup_loader
    def user_loader_callback(_jwt_header, jwt_payload) -> models.User | None:
        identity = jwt_payload['sub']
        return models.User.get_one(username=identity)

    # pylint: disable=unused-variable
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_payload: dict) -> bool:
        return models.Token.is_revoked(jwt_payload)

    @login_manager.user_loader
    def user_lookup_callback(username):
        return models.User.get_one(username=username)

    with app.app_context():
        models.db.create_all()
        if create_default_user:
            models.User.check_if_empty(
                app.config['DASH']['DEFAULT_ADMIN_USERNAME'],
                app.config['DASH']['DEFAULT_ADMIN_PASSWORD'])
        models.Token.prune_database(all_csrf=True)

    app.register_blueprint(custom_tags)
    proxy_depth = app.config['DASH'].get('PROXY_DEPTH', 0)
    if isinstance(proxy_depth, str):
        proxy_depth = int(proxy_depth, 10)
    if proxy_depth > 0:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=proxy_depth, x_proto=proxy_depth,
            x_host=proxy_depth, x_prefix=proxy_depth
        )
    if wss:
        socketio = SocketIO(app, async_mode='threading')
        wss = WebsocketHandler(socketio)
        socketio.on_event('connect', wss.connect)
        socketio.on_event('disconnect', wss.disconnect)
        socketio.on_event('cmd', wss.event_handler)
    return app
