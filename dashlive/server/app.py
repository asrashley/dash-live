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
from pathlib import Path
from typing import Optional

from flask import Flask, request  # type: ignore
from flask_login import LoginManager
from sqlalchemy import delete  # type: ignore
from werkzeug.routing import BaseConverter  # type: ignore

from dashlive.server import models
from dashlive.templates.tags import custom_tags
from dashlive.utils.json_object import JsonObject
from .anonymous_user import AnonymousUser
from .routes import routes
from .settings import (
    cookie_secret, jwt_secret, default_admin_username, default_admin_password,
)

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
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///models.db3"
    app.config['JWT_TOKEN_LOCATION'] = ['cookies']
    app.config['JWT_SECRET_KEY'] = jwt_secret
    app.config['UPLOAD_FOLDER'] = str(media_folder / "blobs")
    app.config['BLOB_FOLDER'] = str(media_folder / "blobs")
    if config is not None:
        app.config.update(config)
    app.secret_key = cookie_secret
    models.db.init_app(app)
    login_manager.anonymous_user = AnonymousUser
    login_manager.init_app(app)

    @login_manager.user_loader
    def user_lookup_callback(username):
        return models.User.get_one(username=username)

    with app.app_context():
        models.db.create_all()
        if create_default_user:
            models.User.check_if_empty(default_admin_username, default_admin_password)
        stmt = delete(models.Token).where(models.Token.token_type == models.TokenType.CSRF)
        models.db.session.execute(stmt)

    app.register_blueprint(custom_tags)
    return app
