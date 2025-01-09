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

import base64
from dataclasses import dataclass
import datetime
import hashlib
import hmac
import logging
import secrets
from typing import ClassVar, TypedDict
import urllib.parse

import flask  # type: ignore

from dashlive.server.models.token import Token, TokenType, KEY_LIFETIMES
from dashlive.server.models import db
from dashlive.utils.json_object import JsonObject

from .exceptions import CsrfFailureException
from .utils import is_https_request

class CsrfTokenCollectionJson(TypedDict):
    files: str
    kids: str
    streams: str
    upload: str | None

@dataclass(slots=True, kw_only=True)
class CsrfTokenCollection:
    files: str
    kids: str
    streams: str
    upload: str | None = None

    def to_dict(self) -> CsrfTokenCollectionJson:
        rv: CsrfTokenCollectionJson = {
            'files': self.files,
            'kids': self.kids,
            'streams': self.streams,
            'upload': self.upload,
        }
        return rv


class CsrfProtection:
    CSRF_COOKIE_NAME: ClassVar[str] = 'csrf'

    @classmethod
    def generate_cookie(cls) -> str:
        """
        generate a secure cookie if not already present
        """
        try:
            return flask.request.cookies[cls.CSRF_COOKIE_NAME]
        except KeyError:
            pass
        csrf_key = secrets.token_urlsafe(Token.CSRF_KEY_LENGTH)
        secure = None
        if is_https_request():
            secure = True

        @flask.after_this_request
        def set_csrf_cookie(response):
            nonlocal secure, csrf_key
            max_age: int = int(KEY_LIFETIMES[TokenType.CSRF].total_seconds())
            response.set_cookie(
                CsrfProtection.CSRF_COOKIE_NAME, csrf_key, httponly=True,
                samesite='Strict', max_age=max_age, secure=secure)
            return response

        return csrf_key

    @classmethod
    def generate_token(cls, service: str, csrf_key: str) -> str:
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
        salt = secrets.token_urlsafe(Token.CSRF_SALT_LENGTH)
        salt = salt[:Token.CSRF_SALT_LENGTH]
        logging.debug(f'generate_csrf salt: "{salt}"')
        # print('generate', service, csrf_key, origin, flask.request.headers['User-Agent'], salt)
        sig.update(bytes(service, 'utf-8'))
        if strict_origin:
            sig.update(bytes(origin, 'utf-8'))
        sig.update(bytes(salt, 'utf-8'))
        rv = urllib.parse.quote(salt + str(base64.b64encode(sig.digest())))
        # print('csrf', service, rv)
        return rv

    @classmethod
    def check(cls, service: str, csrf_token: str) -> None:
        """
        check that the CSRF token from the cookie and the submitted form match
        """
        logging.debug(f'check_csrf service: "{service}"')
        try:
            csrf_key = flask.request.cookies[cls.CSRF_COOKIE_NAME]
        except KeyError:
            logging.debug("csrf cookie not present")
            logging.debug('%s', flask.request.cookies)
            raise CsrfFailureException(
                f"{cls.CSRF_COOKIE_NAME} cookie not present")
        if not csrf_key:
            logging.debug("csrf deserialize failed")

            @flask.after_this_request
            def clear_csrf_cookie(response):
                response.delete_cookie(CsrfProtection.CSRF_COOKIE_NAME)
                return response

            raise CsrfFailureException("csrf cookie not valid")
        logging.debug(f'check_csrf csrf_key: "{csrf_key}"')
        token = str(urllib.parse.unquote(csrf_token))
        try:
            origin = flask.request.headers['Origin']
        except KeyError:
            logging.debug(
                f"No origin in request, using: {flask.request.url}")
            cur_url = urllib.parse.urlparse(flask.request.url, 'http')
            origin = '{}://{}'.format(cur_url.scheme, cur_url.netloc)
        logging.debug(f'check_csrf origin: "{origin}"')
        existing_key = Token.get(jti=token, token_type=TokenType.CSRF)
        if existing_key is not None:
            raise CsrfFailureException("Re-use of csrf_token")
        expires = datetime.datetime.now() + KEY_LIFETIMES[TokenType.CSRF]
        existing_key = Token(
            jti=token, token_type=TokenType.CSRF, expires=expires, revoked=False)
        db.session.add(existing_key)
        salt = token[:Token.CSRF_SALT_LENGTH]
        logging.debug(f'check_csrf salt: "{salt}"')
        token = token[Token.CSRF_SALT_LENGTH:]
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
