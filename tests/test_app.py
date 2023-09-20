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

import ctypes
import os
import logging
import multiprocessing
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import flask

from dashlive.server import models
from dashlive.server.app import create_app

from .mixins.mixin import TestCaseMixin

class TestAppConfig(TestCaseMixin, unittest.TestCase):
    _temp_dir = multiprocessing.Array(ctypes.c_char, 1024)

    config = {
        'FLASK_SECRET_KEY': 'flask.secret',
        'FLASK_DASH__CSRF_SECRET': 'csrf.secret',
        'FLASK_DASH__DEFAULT_ADMIN_USERNAME': 'default.admin',
        'FLASK_DASH__DEFAULT_ADMIN_PASSWORD': 'default.password',
        'FLASK_DASH__ALLOWED_DOMAINS': 'allowed.domains',
        'FLASK_SQLALCHEMY_DATABASE_URI': "sqlite:///:memory:",
        'FLASK_TESTING': "True"
    }

    @patch.dict('dashlive.server.app.environ', config, clear=True)
    def test_set_config_from_environment(self) -> None:
        flask_app = create_app(create_default_user=False)
        with flask_app.app_context():
            self.assertEqual(flask.current_app.config['SECRET_KEY'], 'flask.secret')
            cfg = flask.current_app.config['DASH']
            self.assertEqual(cfg['CSRF_SECRET'], 'csrf.secret')
            self.assertEqual(cfg['DEFAULT_ADMIN_USERNAME'], 'default.admin')
            self.assertEqual(cfg['DEFAULT_ADMIN_PASSWORD'], 'default.password')
            self.assertEqual(cfg['ALLOWED_DOMAINS'], 'allowed.domains')

    @patch.dict('dashlive.server.app.environ', config, clear=True)
    def test_creates_default_admin_account(self) -> None:
        flask_app = create_app(create_default_user=True)
        with flask_app.app_context():
            user = models.User.get(username='default.admin')
            self.assertIsNotNone(user)
            self.assertTrue(user.check_password('default.password'))

    @patch.dict('dashlive.server.app.environ', {}, clear=True)
    def test_set_config_from_file(self) -> None:
        tmpdir = self.create_temp_folder()
        env_filename = tmpdir / 'test.env'
        with env_filename.open('wt', encoding='ascii') as dest:
            dest.write("FLASK_DASH__ALLOWED_DOMAINS='a.domain'\n")
            dest.write("FLASK_DASH__CSRF_SECRET='test.csrf.secret'\n")
            dest.write("FLASK_DASH__DEFAULT_ADMIN_USERNAME='admin'\n")
            dest.write("FLASK_DASH__DEFAULT_ADMIN_PASSWORD='t3st.secret!'\n")
            dest.write("FLASK_SECRET_KEY='cookie.secret'\n")
            dest.write("FLASK_SQLALCHEMY_DATABASE_URI='sqlite:///:memory:'\n")
            dest.write("FLASK_TESTING='True'\n")
        self.assertTrue(env_filename.exists())
        os.environ['DASHLIVE_SETTINGS'] = str(env_filename)
        flask_app = create_app(create_default_user=False)
        with flask_app.app_context():
            self.assertEqual(flask.current_app.config['SECRET_KEY'], 'cookie.secret')
            cfg = flask.current_app.config['DASH']
            self.assertEqual(cfg['CSRF_SECRET'], 'test.csrf.secret')
            self.assertEqual(cfg['DEFAULT_ADMIN_USERNAME'], 'admin')
            self.assertEqual(cfg['DEFAULT_ADMIN_PASSWORD'], 't3st.secret!')
            self.assertEqual(cfg['ALLOWED_DOMAINS'], 'a.domain')

    def create_temp_folder(self) -> Path:
        tmpdir = tempfile.mkdtemp()
        self._temp_dir.value = bytes(tmpdir, 'utf-8')
        return Path(tmpdir)

    def tearDown(self):
        if self._temp_dir.value:
            shutil.rmtree(self._temp_dir.value, ignore_errors=True)
        logging.disable(logging.NOTSET)


if __name__ == '__main__':
    unittest.main()
