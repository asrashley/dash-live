#!/usr/bin/env python
#
import os
import sys

import webapp2

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

from server.routes import webapp_routes
from server.settings import DEBUG
    
app = webapp2.WSGIApplication(webapp_routes, debug=DEBUG)
