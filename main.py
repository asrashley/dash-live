#!/usr/bin/env python
#
import logging
import webapp2

import views
from routes import webapp_routes
from settings import DEBUG
    
app = webapp2.WSGIApplication(webapp_routes, debug=DEBUG)
