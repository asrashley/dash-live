#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import ctypes
import logging
import multiprocessing
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

from dashlive.management.create_db import main
from dashlive.server.app import create_app
from dashlive.server.models.connection import DEFAULT_SQLITE_DATABASE_NAME
from dashlive.server.models.user import User

from .mixins.mixin import TestCaseMixin

class TestCreateDatabase(TestCaseMixin, unittest.TestCase):
    _temp_dir = multiprocessing.Array(ctypes.c_char, 1024)

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir.value = b''

    def tearDown(self) -> None:
        if self._temp_dir.value:
            shutil.rmtree(self._temp_dir.value, ignore_errors=True)
            self._temp_dir.value = b''
        logging.disable(logging.NOTSET)

    def create_temp_folder(self) -> Path:
        tmpdir: str = tempfile.mkdtemp()
        self._temp_dir.value = bytes(tmpdir, 'utf-8')
        return Path(tmpdir)

    @staticmethod
    def make_flask_config(instance: Path) -> dict[str, str]:
        config: dict[str, str] = {
            'FLASK_INSTANCE_PATH': str(instance),
            'FLASK_SECRET_KEY': 'flask.secret',
            'FLASK_DASH__CSRF_SECRET': 'csrf.secret',
            'FLASK_DASH__DEFAULT_ADMIN_USERNAME': 'admin',
            'FLASK_DASH__DEFAULT_ADMIN_PASSWORD': 'password',
            'FLASK_DASH__ALLOWED_DOMAINS': 'allowed.domains',
            'FLASK_TESTING': "True"
        }
        return config

    def test_create_db_using_defaults(self) -> None:
        tmpdir: Path = self.create_temp_folder()
        config: dict[str, str] = self.make_flask_config(tmpdir)

        with patch.dict('dashlive.management.create_db.environ', config, clear=True):
            db_file: Path = tmpdir / DEFAULT_SQLITE_DATABASE_NAME
            self.assertFalse(db_file.exists())
            rv: int = main(["create_db"])
            self.assertEqual(rv, 0)
            self.assertTrue(db_file.exists())
            flask_app: Flask = create_app(create_default_user=False, wss=False)
            with flask_app.app_context():
                user: User | None = User.get(username="admin")
                self.assertIsNotNone(user)
                self.assertTrue(user.check_password(
                    config['FLASK_DASH__DEFAULT_ADMIN_PASSWORD']))

    def test_create_db_with_username(self) -> None:
        tmpdir: Path = self.create_temp_folder()
        config: dict[str, str] = self.make_flask_config(tmpdir)

        with patch.dict('dashlive.management.create_db.environ', config, clear=True):
            db_file: Path = tmpdir / DEFAULT_SQLITE_DATABASE_NAME
            self.assertFalse(db_file.exists())
            rv: int = main(["create_db", "--user", "fred", "--password", "flintstone"])
            self.assertEqual(rv, 0)
            self.assertTrue(db_file.exists())
            flask_app: Flask = create_app(create_default_user=False, wss=False)
            with flask_app.app_context():
                user: User | None = User.get(username="admin")
                self.assertIsNone(user)
                user = User.get(username="fred")
                self.assertTrue(user.check_password("flintstone"))


if __name__ == '__main__':
    unittest.main()
