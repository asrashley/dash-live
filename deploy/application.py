"""
Entry point for DASH server for WSGI and uWSGI environments
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# pylint: disable=wrong-import-position
from dashlive.server.app import create_app

app = create_app(instance_path='/home/dash/instance')
