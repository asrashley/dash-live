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

import logging
import importlib
from os import environ
from pathlib import Path
import secrets

from dotenv import load_dotenv
from flask import Flask, request  # type: ignore
from flask_login import LoginManager
from werkzeug.routing import BaseConverter  # type: ignore

from dashlive.server import models
from dashlive.templates.tags import custom_tags
from dashlive.utils.json_object import JsonObject
from .anonymous_user import AnonymousUser
from .routes import routes

login_manager = LoginManager()

class RegexConverter(BaseConverter):
    """
    Utility class to allow a regex to be used in a route path
    """
    def __init__(self, url_map, *items):
        super().__init__(url_map)
        self.regex = items[0]

def no_api_cache(response):
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
        view_func = getattr(module, handler_name).as_view(name)
        app.add_url_rule(route.template, endpoint=name,
                         view_func=view_func)

def create_app(config: JsonObject | None = None,
               instance_path: str | None = None,
               create_default_user: bool = True) -> Flask:
    load_dotenv(environ.get('DASHLIVE_SETTINGS', '.env'))
    logging.basicConfig()
    srcdir = Path(__file__).parent.resolve()
    basedir = srcdir.parent.parent
    template_folder = basedir / "templates"
    static_folder = basedir / "static"
    if not template_folder.exists():
        template_folder = srcdir / "templates"
        static_folder = srcdir / "static"
    if instance_path is None:
        media_folder = basedir / "media"
    else:
        media_folder = Path(instance_path) / "media"
        if not media_folder.exists():
            media_folder.mkdir()
    app = Flask(
        __name__,
        instance_path=instance_path,
        template_folder=str(template_folder),
        static_folder=str(static_folder))
    add_routes(app)
    dash_settings = {
        'CSRF_SECRET': secrets.token_urlsafe(16),
        'DEFAULT_ADMIN_USERNAME': 'admin',
        'DEFAULT_ADMIN_PASSWORD': secrets.token_urlsafe(10),
    }
    app.config.update(
        BLOB_FOLDER=str(media_folder / "blobs"),
        SQLALCHEMY_DATABASE_URI="sqlite:///models.db3",
        UPLOAD_FOLDER=str(media_folder / "blobs"),
        DASH=dash_settings,
        SECRET_KEY=secrets.token_urlsafe(16)
    )
    app.config.from_prefixed_env()
    if config is not None:
        app.config.update(config)
    log_level = app.config.get('LOG_LEVEL')
    if log_level:
        logging.getLogger().setLevel(log_level.upper())
    for module in ['fio', 'mp4']:
        log_level = app.config.get(f'{module.upper()}_LOG_LEVEL', 'warning')
        logging.getLogger(module).setLevel(log_level.upper())
    models.db.init_app(app)
    login_manager.anonymous_user = AnonymousUser
    login_manager.init_app(app)

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
    return app
