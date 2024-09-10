#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from os import environ

import flask  # type: ignore

def is_ajax() -> bool:
    return (
        flask.request.is_json or
        flask.request.form.get("ajax", "0") == "1" or
        flask.request.args.get("ajax", "0") == "1")

def is_https_request() -> bool:
    if flask.request.scheme == 'https':
        return True
    if environ.get('HTTPS', 'off') == 'on':
        return True
    if flask.request.headers.get('X-Forwarded-Proto', 'http') == 'https':
        return True
    return flask.request.headers.get('X-HTTP-Scheme', 'http') == 'https'
