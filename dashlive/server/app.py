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
from pathlib import Path
from typing import Optional

from flask import Flask  # type: ignore
from flask_login import LoginManager

from dashlive.server import models
from dashlive.templates.tags import custom_tags
from dashlive.utils.json_object import JsonObject
from .routes import add_routes
from .settings import (
    cookie_secret, jwt_secret, default_admin_username, default_admin_password,
)

login_manager = LoginManager()

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
    login_manager.init_app(app)

    @login_manager.user_loader
    def user_lookup_callback(username):
        return models.User.get_one(username=username)

    with app.app_context():
        models.db.create_all()
        if create_default_user:
            models.User.check_if_empty(default_admin_username, default_admin_password)

    app.register_blueprint(custom_tags)
    return app
