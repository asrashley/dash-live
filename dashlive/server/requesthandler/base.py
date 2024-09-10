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
from typing import AbstractSet, Any

import base64
import datetime
import hashlib
import hmac
import logging
import re
import secrets
import urllib.request
import urllib.parse
import urllib.error
import urllib.parse

import flask  # type: ignore
from flask.views import MethodView  # type: ignore
from flask_login import current_user

from dashlive.server import models
from dashlive.server.routes import routes, Route
from dashlive.server.options.container import OptionsContainer
from dashlive.server.options.repository import OptionsRepository
from dashlive.utils import objects
from dashlive.utils.json_object import JsonObject

from .exceptions import CsrfFailureException
from .utils import is_https_request

class RequestHandlerBase(MethodView):
    CLIENT_COOKIE_NAME = 'dash'
    CSRF_COOKIE_NAME = 'csrf'
    CSRF_EXPIRY = 1200
    DEFAULT_ALLOWED_DOMAINS = re.compile(
        r'^http://(dashif\.org)|(shaka-player-demo\.appspot\.com)|(mediapm\.edgesuite\.net)')
    INJECTED_ERROR_CODES = [404, 410, 503, 504]

    def create_context(self, **kwargs):
        context = {
            "http_protocol": flask.request.scheme,
        }
        context.update(kwargs)
        if current_user.is_authenticated:
            context["is_current_user_admin"] = current_user.is_admin
        context['remote_addr'] = flask.request.remote_addr
        context['request_uri'] = flask.request.url
        if is_https_request():
            context['request_uri'] = context['request_uri'].replace(
                'http://', 'https://')
        return context

    def generate_csrf_cookie(self) -> str:
        """
        generate a secure cookie if not already present
        """
        try:
            return flask.request.cookies[self.CSRF_COOKIE_NAME]
        except KeyError:
            pass
        csrf_key = secrets.token_urlsafe(models.Token.CSRF_KEY_LENGTH)
        secure = None
        if is_https_request():
            secure = True

        @flask.after_this_request
        def set_csrf_cookie(response):
            response.set_cookie(
                self.CSRF_COOKIE_NAME, csrf_key, httponly=True,
                samesite='Strict', max_age=self.CSRF_EXPIRY, secure=secure)
            return response

        return csrf_key

    def generate_csrf_token(self, service: str, csrf_key: str) -> str:
        """
        generate a CSRF token that can be used as a hidden form field
        """
        logging.debug(f'generate_csrf service: "{service}"')
        logging.debug(f'generate_csrf csrf_key: "{csrf_key}"')
        # logging.debug(f'generate_csrf URL: {url}')
        # logging.debug(
        # 'generate_csrf User-Agent: "{}"'.format(flask.request.headers['User-Agent']))
        cfg = flask.current_app.config['DASH']
        strict_origin = cfg.get('STRICT_CSRF_ORIGIN', 'False').lower() == 'true'

        sig = hmac.new(
            bytes(cfg['CSRF_SECRET'], 'utf-8'),
            bytes(csrf_key, 'utf-8'),
            hashlib.sha1)
        cur_url = urllib.parse.urlparse(flask.request.url, 'http')
        origin = '{}://{}'.format(cur_url.scheme, cur_url.netloc)
        logging.debug(f'generate_csrf origin: "{origin}"')
        salt = secrets.token_urlsafe(models.Token.CSRF_SALT_LENGTH)
        salt = salt[:models.Token.CSRF_SALT_LENGTH]
        logging.debug(f'generate_csrf salt: "{salt}"')
        # print('generate', service, csrf_key, origin, flask.request.headers['User-Agent'], salt)
        sig.update(bytes(service, 'utf-8'))
        if strict_origin:
            sig.update(bytes(origin, 'utf-8'))
        sig.update(bytes(salt, 'utf-8'))
        rv = urllib.parse.quote(salt + str(base64.b64encode(sig.digest())))
        # print('csrf', service, rv)
        return rv

    def check_csrf(self, service, params):
        """
        check that the CSRF token from the cookie and the submitted form match
        """
        logging.debug(f'check_csrf service: "{service}"')
        try:
            csrf_key = flask.request.cookies[self.CSRF_COOKIE_NAME]
        except KeyError:
            logging.debug("csrf cookie not present")
            logging.debug(str(flask.request.cookies))
            raise CsrfFailureException(
                f"{self.CSRF_COOKIE_NAME} cookie not present")
        if not csrf_key:
            logging.debug("csrf deserialize failed")

            @flask.after_this_request
            def clear_csrf_cookie(response):
                response.delete_cookie(self.CSRF_COOKIE_NAME)
                return response

            raise CsrfFailureException("csrf cookie not valid")
        logging.debug(f'check_csrf csrf_key: "{csrf_key}"')
        try:
            token = str(urllib.parse.unquote(params['csrf_token']))
        except KeyError:
            raise CsrfFailureException("csrf_token not present")
        try:
            origin = flask.request.headers['Origin']
        except KeyError:
            logging.debug(
                f"No origin in request, using: {flask.request.url}")
            cur_url = urllib.parse.urlparse(flask.request.url, 'http')
            origin = '{}://{}'.format(cur_url.scheme, cur_url.netloc)
        logging.debug(f'check_csrf origin: "{origin}"')
        existing_key = models.Token.get(jti=token,
                                        token_type=models.TokenType.CSRF)
        if existing_key is not None:
            raise CsrfFailureException("Re-use of csrf_token")
        expires = datetime.datetime.now() + datetime.timedelta(seconds=self.CSRF_EXPIRY)
        existing_key = models.Token(
            jti=token, token_type=models.TokenType.CSRF,
            expires=expires, revoked=False)
        models.db.session.add(existing_key)
        salt = token[:models.Token.CSRF_SALT_LENGTH]
        logging.debug(f'check_csrf salt: "{salt}"')
        token = token[models.Token.CSRF_SALT_LENGTH:]
        cfg = flask.current_app.config['DASH']
        strict_origin = cfg.get('STRICT_CSRF_ORIGIN', 'False').lower() == 'true'
        sig = hmac.new(
            bytes(cfg['CSRF_SECRET'], 'utf-8'),
            bytes(csrf_key, 'utf-8'),
            hashlib.sha1)
        sig.update(bytes(service, 'utf-8'))
        if strict_origin:
            sig.update(bytes(origin, 'utf-8'))
        # logging.debug("check_csrf Referer: {}".format(flask.request.headers['Referer']))
        sig.update(bytes(salt, 'utf-8'))
        b64_sig = str(base64.b64encode(sig.digest()))
        if token != b64_sig:
            logging.debug("signatures do not match: %s %s", token, b64_sig)
            raise CsrfFailureException("signatures do not match")
        return True

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

    def add_allowed_origins(self, headers):
        cfg = flask.current_app.config['DASH']
        allowed_domains = cfg.get('ALLOWED_DOMAINS', self.DEFAULT_ALLOWED_DOMAINS)
        if allowed_domains == "*":
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Access-Control-Allow-Methods"] = "HEAD, GET, POST"
            return
        try:
            if isinstance(allowed_domains, str):
                allowed_domains = re.compile(allowed_domains)
            if allowed_domains.search(flask.request.headers['Origin']):
                headers["Access-Control-Allow-Origin"] = flask.request.headers['Origin']
                headers["Access-Control-Allow-Methods"] = "HEAD, GET, POST"
        except KeyError:
            pass

    def has_http_range(self):
        return 'range' in flask.request.headers

    def get_http_range(self, content_length):
        try:
            http_range = flask.request.headers['range'].lower().strip()
        except KeyError:
            return (None, None, 200, {})
        if not http_range.startswith('bytes='):
            raise ValueError('Only byte based ranges are supported')
        if ',' in http_range:
            raise ValueError('Multiple ranges not supported')
        start, end = http_range[6:].split('-')
        if start == '':
            amount = int(end, 10)
            start = content_length - amount
            end = content_length - 1
        elif end == '':
            end = content_length - 1
        if isinstance(start, str):
            start = int(start, 10)
        if isinstance(end, str):
            end = int(end, 10)
        status = 206
        headers = {
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

    def jsonify(self, data: Any, status: int | None = None,
                headers: dict | None = None) -> flask.Response:
        """
        Replacement for Flask jsonify that uses flatten to convert non-json objects
        """
        if status is None:
            status = 200
        if isinstance(data, dict):
            response = flask.json.jsonify(**objects.flatten(data))
        elif isinstance(data, list):
            response = flask.json.jsonify(objects.flatten(data))
        else:
            response = flask.json.jsonify(data)
        response.status = status
        if headers is None:
            headers = {}
            self.add_allowed_origins(headers)
        response.headers.update(headers)
        return response

    def jsonify_no_content(self, status: int) -> flask.Response:
        """
        Used to return a JSON response with no body
        """
        response = flask.json.jsonify('')
        response.status = status
        return response

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
        navbar = [{
            'title': 'Home', 'href': flask.url_for('home')
        }, {
            'title': 'Streams', 'href': flask.url_for('list-streams')
        }, {
            'title': 'Validate', 'href': flask.url_for('validate-stream')
        }]
        if current_user.is_authenticated:
            if current_user.is_admin:
                navbar.append({
                    'title': 'Users', 'href': flask.url_for('list-users')
                })
            else:
                navbar.append({
                    'title': 'My Account', 'href': flask.url_for('change-password')
                })
            navbar.append({
                'title': 'Log Out',
                'class': 'user-login',
                'href': flask.url_for('logout')
            })
        else:
            navbar.append({
                'title': 'Log In',
                'class': 'user-login',
                'href': flask.url_for('login')
            })
        found_active = False
        for nav in navbar[1:]:
            if flask.request.path.startswith(nav['href']):
                nav['active'] = True
                found_active = True
                break
        if not found_active:
            navbar[0]['active'] = True
        context.update({
            "title": kwargs.get('title', route.title),
            "breadcrumbs": self.get_breadcrumbs(route),
            "navbar": navbar,
            'routes': routes,
        })
        return context

    def get_breadcrumbs(self, route: Route) -> list[dict[str, str]]:
        breadcrumbs = [{
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
            return flask.make_response(f'CSRF failure: {err}', 400)
        model = self.get_model_dict()
        result = self.delete_model()
        if not result.get('error'):
            flask.flash(f'Deleted {self.MODEL_NAME.lower()} {model["title"]}', 'success')
        return flask.redirect(self.get_next_url())

    def delete(self, **kwargs) -> flask.Response:
        """
        handler for deleting a stream
        """
        result = {"error": None}
        try:
            self.check_csrf(self.CSRF_TOKEN_NAME, flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            result = {
                "error": f'CSRF failure: {err}'
            }
        if result['error'] is None:
            result = self.delete_model()
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token(self.CSRF_TOKEN_NAME, csrf_key)
        return self.jsonify(result)

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
