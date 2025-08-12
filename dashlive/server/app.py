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
import socket

from dotenv import load_dotenv
from flask import Flask, request, Response  # type: ignore
from flask_login import LoginManager
from flask_socketio import SocketIO
from werkzeug.routing import BaseConverter, Map  # type: ignore
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_jwt_extended import JWTManager
from netifaces import interfaces, ifaddresses, AF_INET

from dashlive.server.models.all import create_all_tables
from dashlive.server.models.connection import make_db_connection_string
from dashlive.server.models.content_type import ContentType
from dashlive.server.models.db import db
from dashlive.server.models.token import Token, DecodedJwtToken
from dashlive.server.models.user import User
from dashlive.server.requesthandler.websocket import WebsocketHandler
from dashlive.utils.json_object import JsonObject

from .anonymous_user import AnonymousUser
from .asyncio_loop import AsyncioLoop
from .folders import AppFolders
from .routes import Route, routes, ui_routes
from .template_tags import custom_tags
# from .thread_pool import pool_executor

login_manager = LoginManager()
asyncio_loop = AsyncioLoop()

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

def add_a_route(app: Flask, name: str, route: Route):
    full_path: str = f'dashlive.server.requesthandler.{route.handler}'
    pos: int = full_path.rindex('.')
    module_name: str = full_path[:pos]
    handler_name: str = full_path[pos + 1:]
    module = importlib.import_module(module_name)
    view = getattr(module, handler_name)
    try:
        view_func = view.as_view(name)
    except AttributeError:
        view_func = view
    app.add_url_rule(route.template, endpoint=name, view_func=view_func)

def add_routes(app: Flask) -> None:
    app.url_map.converters['regex'] = RegexConverter
    app.after_request(no_api_cache)
    for name, route in routes.items():
        add_a_route(app, name, route)
        # if name == 'home':
        #    app.add_url_rule(
        #        r'/<path:path>', endpoint='fallback', view_func=view_func)
    for name, route in ui_routes.items():
        add_a_route(app, f"ui-{name}", route)

def create_app(config: JsonObject | None = None,
               instance_path: str | None = None,
               create_default_user: bool = True,
               folders: AppFolders | None = None,
               wss: bool = True) -> Flask:
    if config is None:
        load_dotenv(environ.get('DASHLIVE_SETTINGS', '.env'))
    logging.basicConfig()
    if folders is None:
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
        instance_path=str(folders.instance_path),
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
    log_level: str | None = app.config.get('LOG_LEVEL')
    if log_level:
        logging.getLogger().setLevel(log_level.upper())
    for module in ['fio', 'mp4']:
        log_level = app.config.get(f'{module.upper()}_LOG_LEVEL', 'warning')
        log = logging.getLogger(module)
        log.setLevel(log_level.upper())
    db.init_app(app)
    jwt = JWTManager(app)
    login_manager.anonymous_user = AnonymousUser
    login_manager.init_app(app)

    # pylint: disable=unused-variable
    @jwt.user_lookup_loader
    def user_loader_callback(_jwt_header: dict, jwt_payload: DecodedJwtToken) -> User | None:
        identity: str = jwt_payload['sub']
        return User.get_one(username=identity)

    # pylint: disable=unused-variable
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header: dict, jwt_payload: DecodedJwtToken) -> bool:
        return Token.is_revoked(jwt_payload)

    @login_manager.user_loader
    def user_lookup_callback(username: str) -> User | None:
        return User.get_one(username=username)

    with app.app_context():
        create_all_tables()
        if create_default_user:
            User.populate_if_empty(
                app.config['DASH']['DEFAULT_ADMIN_USERNAME'],
                app.config['DASH']['DEFAULT_ADMIN_PASSWORD'],
                session=db.session)
        ContentType.populate_if_empty(db.session)
        Token.prune_database(all_csrf=True, session=db.session)
        db.session.commit()

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
        server_name: str = environ.get('SERVER_NAME', '')
        port: str = environ.get('SERVER_PORT', '80')
        if port == '80':
            port = ''
        else:
            port = f':{port}'
        cors_allowed_origins: list[str] = [
            f'http://127.0.0.1{port}',
            f'http://localhost{port}'
        ]
        if server_name:
            cors_allowed_origins.append(f'http://{server_name}{port}')
            cors_allowed_origins.append(f'https://{server_name}{port}')
        if app.debug:
            frontend_port: str = environ.get('FRONTEND_PORT', '8765')
            cors_allowed_origins.append(f"http://127.0.0.1:{frontend_port}")
            cors_allowed_origins.append(f"http://localhost:{frontend_port}")
            for ifaceName in interfaces():
                for i in ifaddresses(ifaceName).setdefault(AF_INET, [{'addr': ''}]):
                    addr = i['addr']
                    if not addr or addr.startswith('127'):
                        continue
                    cors_allowed_origins.append(f"http://{addr}{port}")
                    cors_allowed_origins.append(f"http://{addr}:{frontend_port}")
                    try:
                        hostname: str = socket.gethostbyaddr(addr)[0]
                        cors_allowed_origins.append(f"http://{hostname}{port}")
                        cors_allowed_origins.append(f"http://{hostname}:{frontend_port}")
                    except socket.herror as err:
                        logging.warning('Failed to find hostname for IP address %s: %s', addr, err)
        logging.debug('cors_allowed_origins=%s', cors_allowed_origins)
        socketio = SocketIO(
            app, async_mode='threading', cors_allowed_origins=cors_allowed_origins)
        wss = WebsocketHandler(asyncio_loop, socketio)
        socketio.on_event('connect', wss.connect)
        socketio.on_event('disconnect', wss.disconnect)
        socketio.on_event('cmd', wss.event_handler)
    return app
