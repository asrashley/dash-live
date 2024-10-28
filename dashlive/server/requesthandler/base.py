#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from abc import abstractmethod
import logging
from typing import AbstractSet

import urllib.request
import urllib.parse
import urllib.error
import urllib.parse

import flask  # type: ignore
from flask.views import MethodView  # type: ignore

from dashlive.server import models
from dashlive.server.routes import routes, Route
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.repository import OptionsRepository
from dashlive.utils.json_object import JsonObject

from .csrf import CsrfProtection
from .exceptions import CsrfFailureException
from .navbar import create_navbar_context, NavBarItem
from .template_context import TemplateContext, create_template_context
from .utils import jsonify

class RequestHandlerBase(MethodView):
    CLIENT_COOKIE_NAME = 'dash'
    INJECTED_ERROR_CODES = [404, 410, 503, 504]

    def create_context(self, **kwargs) -> TemplateContext:
        return create_template_context(**kwargs)

    def generate_csrf_cookie(self) -> str:
        """
        generate a secure cookie if not already present
        """
        return CsrfProtection.generate_cookie()

    def generate_csrf_token(self, service: str, csrf_key: str) -> str:
        """
        generate a CSRF token that can be used as a hidden form field
        """
        return CsrfProtection.generate_token(service, csrf_key)

    def check_csrf(self, service: str, params) -> None:
        """
        check that the CSRF token from the cookie and the submitted form match
        """
        try:
            token = params['csrf_token']
        except KeyError:
            raise CsrfFailureException('csrf_token not present')
        CsrfProtection.check(service, token)

    def get_bool_param(self, param: str, default: bool | None = False) -> bool:
        value = flask.request.args.get(param)
        if value is None:
            value = flask.request.form.get(param)
        if value is None:
            return default
        return value.lower() in {"1", "true", "on"}

    def calculate_options(self,
                          mode: str,
                          args: dict[str, str],
                          stream: models.Stream | None = None,
                          features: AbstractSet[str] | None = None,
                          restrictions: dict[str, tuple] | None = None) -> OptionsContainer:
        defaults = OptionsRepository.get_default_options()
        if stream is not None:
            if stream.defaults is not None:
                defaults = defaults.clone(**stream.defaults)
        if restrictions is not None:
            args = {**args}
            for key, allowed_values in restrictions.items():
                try:
                    value = args[key]
                    if value not in allowed_values:
                        if len(allowed_values) == 1:
                            args[key] = list(allowed_values)[0]
                        else:
                            del args[key]
                except KeyError:
                    pass
        options = OptionsRepository.convert_cgi_options(args, defaults=defaults)
        if features is not None:
            options.remove_unsupported_features(features)
        options.add_field('mode', mode)
        return options

    def has_http_range(self) -> bool:
        return 'range' in flask.request.headers

    def get_http_range(self,
                       content_length: int
                       ) -> tuple[int | None, int | None, int, dict[str, str]]:
        try:
            http_range = flask.request.headers['range'].lower().strip()
        except KeyError:
            return (None, None, 200, {})
        if not http_range.startswith('bytes='):
            raise ValueError('Only byte based ranges are supported')
        if ',' in http_range:
            raise ValueError('Multiple ranges not supported')

        start_str: str
        end_str: str
        start: int
        end: int

        start_str, end_str = http_range[6:].split('-')

        if start_str == '':
            amount: int = int(end_str, 10)
            start = content_length - amount
            end = content_length - 1
        else:
            start = int(start_str, 10)
            if end_str == '':
                end = content_length - 1
            else:
                end = int(end_str, 10)

        status: int = 206
        headers: dict[str, str] = {
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {start}-{end}/{content_length}'
        }
        if end >= content_length or end < start:
            headers['Content-Range'] = f'bytes */{content_length}'
            status = 416
        return (start, end, status, headers,)

    def get_next_url(self) -> str | None:
        """
        Returns unquoted "next" URL if present in the request
        """
        next: str | None = None
        # TODO: check "next" is a URL within this app
        try:
            next = flask.request.args['next']
            if next is not None:
                next = urllib.parse.unquote_plus(next)
            if next == "":
                next = None
        except KeyError:
            pass
        return next

    def get_next_url_with_fallback(self, route_name: str, **kwargs) -> str:
        """
        Checks for a "next" parameter in the request
        """
        next = self.get_next_url()
        if next is None:
            next = flask.url_for(route_name, **kwargs)
        return next

    def increment_error_counter(self, usage: str, code: int) -> int:
        key = f'error-{usage}-{code:06d}'
        value = flask.session.get(key, 0) + 1
        flask.session[key] = value
        return value

    def reset_error_counter(self, usage: str, code: int) -> None:
        key = f'error-{usage}-{code:06d}'
        flask.session[key] = None


class HTMLHandlerBase(RequestHandlerBase):
    """
    Base class for all HTML pages
    """

    def create_context(self, **kwargs):
        context = super().create_context(**kwargs)
        if 'nomodule' not in flask.request.args:
            context['nomodule'] = 'nomodule'
        route = routes[flask.request.endpoint]
        navbar = create_navbar_context()
        context.update({
            "title": kwargs.get('title', route.title),
            "breadcrumbs": self.get_breadcrumbs(route),
            "navbar": navbar,
            'routes': routes,
        })
        return context

    def get_breadcrumbs(self, route: Route) -> list[NavBarItem]:
        breadcrumbs: list[NavBarItem] = [{
            'title': route.page_title(),
            'active': 'active'
        }]
        p: str | None = route.parent
        while p:
            rt: Route = routes[p]
            breadcrumbs.insert(0, {
                "title": rt.page_title(),
                "href": flask.url_for(rt.name)
            })
            p = rt.parent
        return breadcrumbs


class DeleteModelBase(HTMLHandlerBase):
    """
    Base class for deleting a model from the database
    """

    MODEL_NAME: str = ''

    def get(self, **kwargs) -> flask.Response:
        """
        Returns HTML form to confirm if stream should be deleted
        """
        context = self.create_context()
        csrf_key = self.generate_csrf_cookie()
        context.update({
            'model': self.get_model_dict(),
            'model_name': self.MODEL_NAME,
            'cancel_url': self.get_cancel_url(),
            'submit_url': flask.request.url,
            'csrf_token': self.generate_csrf_token(self.CSRF_TOKEN_NAME, csrf_key),
        })
        return flask.render_template('delete_model_confirm.html', **context)

    def post(self, **kwargs) -> flask.Response:
        """
        Deletes a model, in response to a submitted confirm form
        """
        try:
            self.check_csrf(self.CSRF_TOKEN_NAME, flask.request.form)
        except (ValueError, CsrfFailureException) as err:
            logging.info('CSRF failure: %s', err)
            return flask.make_response('CSRF failure', 400)
        model = self.get_model_dict()
        result = self.delete_model()
        if not result.get('error'):
            flask.flash(f'Deleted {self.MODEL_NAME.lower()} {model["title"]}', 'success')
        return flask.redirect(self.get_next_url())

    def delete(self, **kwargs) -> flask.Response:
        """
        handler for deleting an item from a model
        """
        result = {"error": None}
        try:
            self.check_csrf(self.CSRF_TOKEN_NAME, flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            logging.info('CSRF failure: %s', err)
            result = {
                "error": 'CSRF failure'
            }
        if result['error'] is None:
            result = self.delete_model()
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token(self.CSRF_TOKEN_NAME, csrf_key)
        return jsonify(result)

    @abstractmethod
    def get_model_dict(self) -> JsonObject:
        pass

    @abstractmethod
    def get_next_url(self) -> str:
        pass

    @abstractmethod
    def get_cancel_url(self) -> str:
        pass

    @abstractmethod
    def delete_model(self) -> JsonObject:
        pass
