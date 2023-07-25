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
from typing import Optional

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

def create_app(config: Optional[JsonObject] = None,
               create_default_user: bool = True) -> Flask:
    logging.basicConfig()
    srcdir = Path(__file__).parent.resolve()
    basedir = srcdir.parent.parent
    template_folder = basedir / "templates"
    static_folder = basedir / "static"
    media_folder = basedir / "media"
    if not template_folder.exists():
        template_folder = srcdir / "templates"
        static_folder = srcdir / "static"
    app = Flask(
        __name__,
        template_folder=str(template_folder),
        static_folder=str(static_folder))
    add_routes(app)
    dash_settings = {
        'CSRF_SECRET': secrets.token_urlsafe(16),
        'default_admin_username': 'admin',
        'default_admin_password': secrets.token_urlsafe(10),
    }
    app.config.update(
        BLOB_FOLDER=str(media_folder / "blobs"),
        SQLALCHEMY_DATABASE_URI="sqlite:///models.db3",
        UPLOAD_FOLDER=str(media_folder / "blobs"),
        DASH=dash_settings,
        SECRET_KEY=secrets.token_urlsafe(16)
    )
    if config is None:
        app.config.from_object('dashlive.server.settings')
    if 'DASHLIVE_SETTINGS' in environ:
        app.config.from_envvar('DASHLIVE_SETTINGS')
    if config is not None:
        app.config.update(config)
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
                app.config['DASH']['default_admin_username'],
                app.config['DASH']['default_admin_password'])
        models.Token.prune_database(all_csrf=True)

    app.register_blueprint(custom_tags)
    return app
