#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from flask import Response, make_response
from flask.views import MethodView  # type: ignore

from .utils import is_ajax, jsonify_no_content

class NotFound(MethodView):
    """
    Handler that will always return a 404 error
    """

    def head(self, **kwargs) -> Response:
        return self.get()

    def get(self, **kwargs) -> Response:
        if is_ajax():
            return jsonify_no_content(404)
        return make_response('Not Found', 404)
