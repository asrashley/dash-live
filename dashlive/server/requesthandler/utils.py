#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from os import environ
import re
from typing import Any, Pattern
import urllib.parse

import flask  # type: ignore

from dashlive.utils.objects import flatten

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


DEFAULT_ALLOWED_DOMAINS = re.compile(
    r'^http://(dashif\.org)|(shaka-player-demo\.appspot\.com)|(mediapm\.edgesuite\.net)')

DEFAULT_ALLOWED_METHODS: set[str] = {'HEAD', 'GET', 'POST'}

def add_allowed_origins(headers: dict[str, str],
                        methods: set[str] | None = None) -> None:
    """
    Adds access control headers to the HTTP headers object
    """
    allowed_domains: str | Pattern | None = flask.g.get('allowed_domains', None)

    try:
        origin: str = flask.request.headers['Origin']
    except KeyError:
        parts = urllib.parse.urlsplit(flask.request.url)
        origin = f"{parts.scheme}://{parts.netloc}"
    if allowed_domains is None:
        cfg = flask.current_app.config['DASH']
        allowed_domains = cfg.get('ALLOWED_DOMAINS', DEFAULT_ALLOWED_DOMAINS)
        if isinstance(allowed_domains, str) and allowed_domains != "*":
            allowed_domains = re.compile(allowed_domains)
        flask.g.allowed_domains = allowed_domains
    if methods is None:
        methods = DEFAULT_ALLOWED_METHODS
    if allowed_domains == "*":
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Methods"] = ", ".join(methods)
        return
    try:
        if allowed_domains.search(origin):
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Methods"] = ", ".join(methods)
    except KeyError:
        pass


def jsonify(data: Any, status: int | None = None,
            headers: dict[str, str] | None = None) -> flask.Response:
    """
    Replacement for Flask jsonify that uses flatten to convert non-json objects
    """
    if status is None:
        status = 200
    if isinstance(data, dict):
        response = flask.json.jsonify(**flatten(data))
    elif isinstance(data, list):
        response = flask.json.jsonify(flatten(data))
    else:
        response = flask.json.jsonify(data)
    response.status = status
    if headers is None:
        headers = {}
        add_allowed_origins(headers)
    response.headers.update(headers)
    return response

def jsonify_no_content(status: int) -> flask.Response:
    """
    Used to return a JSON response with no body
    """
    response = flask.json.jsonify('')
    response.status = status
    return response
