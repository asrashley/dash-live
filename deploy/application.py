"""
Entry point for DASH server for WSGI and uWSGI environments
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# pylint: disable=wrong-import-position
from dashlive.server.app import create_app

instance_path = os.environ.get('FLASK_INSTANCE_PATH', '/home/dash/instance')

app = create_app(instance_path=instance_path)
