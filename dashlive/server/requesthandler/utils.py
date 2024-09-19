#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from os import environ

import flask  # type: ignore
from langcodes import standardize_tag

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
