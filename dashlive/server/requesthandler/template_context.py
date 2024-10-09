#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import TypedDict

import flask  # type: ignore
from flask_login import current_user

from .utils import is_https_request

class TemplateContext(TypedDict):
    http_protocol: str
    is_current_user_admin: bool
    remote_addr: str
    request_uri: str
    title: str


def create_template_context(title: str | None = None, **kwargs) -> TemplateContext:
    if title is None:
        title = 'DASH'
    is_admin: bool = False
    if current_user.is_authenticated:
        is_admin = current_user.is_admin
    context: TemplateContext = {
        'http_protocol': flask.request.scheme,
        'is_current_user_admin': is_admin,
        'remote_addr': flask.request.remote_addr,
        'request_uri': flask.request.url,
        'title': title
    }
    if is_https_request():
        context['request_uri'] = context['request_uri'].replace(
            'http://', 'https://')
    context.update(kwargs)
    return context
