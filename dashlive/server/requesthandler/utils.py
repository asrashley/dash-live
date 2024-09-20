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

import flask  # type: ignore
from langcodes import standardize_tag

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

def add_allowed_origins(headers: dict[str, str]) -> None:
    """
    Adds access control headers to the HTTP headers object
    """
    allowed_domains: str | Pattern | None = flask.g.get('allowed_domains', None)

    if allowed_domains is None:
        cfg = flask.current_app.config['DASH']
        allowed_domains = cfg.get('ALLOWED_DOMAINS', DEFAULT_ALLOWED_DOMAINS)
        if isinstance(allowed_domains, str) and allowed_domains != "*":
            allowed_domains = re.compile(allowed_domains)
        flask.g.allowed_domains = allowed_domains
    if allowed_domains == "*":
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Access-Control-Allow-Methods"] = "HEAD, GET, POST"
        return
    try:
        if allowed_domains.search(flask.request.headers['Origin']):
            headers["Access-Control-Allow-Origin"] = flask.request.headers['Origin']
            headers["Access-Control-Allow-Methods"] = "HEAD, GET, POST"
    except KeyError:
        pass

UNDEFINED_LANGS: set[str | None] = {'und', 'zxx', None}

def lang_is_equal(a: str | None,
                  b: str | None,
                  match_undefined: bool = False) -> bool:
    if a == b:
        return True
    if match_undefined:
        if a in UNDEFINED_LANGS:
            return True
        if b in UNDEFINED_LANGS:
            return True
    if a is None or b is None:
        return False
    try:
        a = standardize_tag(a)
        b = standardize_tag(b)
    except ValueError:
        return False
    return a == b
