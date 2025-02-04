#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime
from typing import NotRequired, TypedDict, cast

import flask
from flask_jwt_extended import get_current_user, get_jwt, jwt_required, current_user as jwt_current_user
from flask_login import current_user, login_user, logout_user
from flask.views import MethodView

from dashlive.server.models.db import db
from dashlive.server.models.group import Group
from dashlive.server.models.token import EncodedJWTokenJson, TokenType, Token
from dashlive.server.models.user import User, UserSummaryJson
from dashlive.utils.json_object import JsonObject

from .base import HTMLHandlerBase
from .csrf import CsrfProtection, CsrfTokenCollection
from .decorators import login_required, jwt_login_required
from .utils import jsonify, jsonify_no_content


class LoginResponseJson(TypedDict):
    success: bool
    csrfToken: str
    accessToken: NotRequired[str]
    refreshToken: NotRequired[str]
    user: UserSummaryJson

class LoginPage(HTMLHandlerBase):
    """
    handler for logging into the site
    """

    @jwt_required(refresh=True)
    def get(self) -> flask.Response:
        user: User = cast(User, jwt_current_user)
        csrf_key: str = CsrfProtection.generate_cookie()
        access_token: EncodedJWTokenJson = Token.generate_api_token(user, TokenType.ACCESS).toJSON()
        user_json: UserSummaryJson = user.summary()
        result: LoginResponseJson = {
            'success': True,
            'csrfToken': self.generate_csrf_token('login', csrf_key),
            'accessToken': access_token,
            'user': user_json,
        }

        return jsonify(result)

    def post(self) -> flask.Response:
        data: JsonObject = flask.request.json
        username: str | None = data.get("username", None)
        password: str | None = data.get("password", None)
        rememberme: bool = data.get("rememberme", False)
        user: User | None = User.get_one(username=username)
        if not user:
            user = User.get_one(email=username)
        if user is None or not user.check_password(password):
            csrf_key: str = self.generate_csrf_cookie()
            result: LoginResponseJson = {
                'error': "Wrong username or password",
                'csrf_token': self.generate_csrf_token('login', csrf_key),
                'success': False,
            }
            return jsonify(result)
        login_user(user, remember=rememberme)
        user.last_login = datetime.datetime.now()
        db.session.commit()
        csrf_key = self.generate_csrf_cookie()
        access_token: Token = Token.generate_api_token(user, TokenType.ACCESS)
        refresh_token: Token = Token.generate_api_token(current_user, TokenType.REFRESH)
        result: LoginResponseJson = {
            'success': True,
            'mustChange': user.must_change,
            'csrf_token': self.generate_csrf_token('login', csrf_key),
            'accessToken': access_token.toJSON(),
            'refreshToken': refresh_token.toJSON(),
            'user': user.to_dict(only={'email', 'username', 'pk', 'last_login'}),
        }
        result['user']['groups'] = user.get_groups()
        return jsonify(result)

    @jwt_required()
    def delete(self) -> flask.Response:
        for token in jwt_current_user.tokens:
            token.revoked = True
        jti: str = get_jwt()["jti"]
        refresh_token: Token | None = Token.get_one(jti=jti, token_type=TokenType.REFRESH.value)
        if refresh_token is None:
            refresh_token = Token(jti=jti, token_type=TokenType.REFRESH.value, user=jwt_current_user)
            db.session.add(refresh_token)
        refresh_token.revoked = True
        db.session.commit()
        logout_user()
        return jsonify_no_content(204)


class LogoutPage(HTMLHandlerBase):
    """
    Logs user out of site
    """
    def get(self) -> flask.Response:
        if current_user.is_authenticated:
            for token in current_user.tokens:
                token.revoked = True
        logout_user()
        db.session.commit()
        return flask.redirect(flask.url_for('ui-home'))

class AddEditUserResponse(TypedDict):
    success: bool
    errors: list[str]
    user: NotRequired[UserSummaryJson]


class ListUsers(HTMLHandlerBase):
    decorators = [
        jwt_login_required(admin=True),
        jwt_required(),
    ]

    def get(self) -> flask.Response:
        """
        List all user accounts
        """
        users: list[UserSummaryJson] = []
        guest: User = User.get_guest_user()
        for user in User.all():
            if user.pk == guest.pk:
                continue
            users.append(user.summary())
        return jsonify(users)

    def put(self) -> flask.Response:
        """
        Add a new user
        """
        js = flask.request.json
        result: AddEditUserResponse = {
            "errors": [],
            "success": False,
        }
        username: str | None = js.get("username")
        email: str | None = js.get("email")
        password: str | None = js.get("password")
        confirm: str | None = js.get("confirmPassword")
        if username is None or username == "":
            result["errors"].append('Username is required')
        elif User.count(username=username) > 0:
            result["errors"].append(f'User {username} already exists')
        if email is None or email == "":
            result["errors"].append('email is required')
        elif User.count(email=email) > 0:
            result["errors"].append(f'Email address {email} already exists')
        if password is None or confirm is None:
            result["errors"].append('password is required')
        elif password != confirm:
            result["errors"].append('passwords do not match')
        groups: list[Group] = []
        for group in Group.names():
            field_name: str = f'{group.lower()}Group'
            if js.get(field_name, False):
                groups.append(group)
        if not result['errors']:
            result['success'] = True
            user = User(username=username, email=email, must_change=js.get('mustChange', False))
            user.set_password(password)
            user.set_groups(groups)
            db.session.add(user)
            db.session.commit()
            result["user"] = user.summary()
        return jsonify(result)


class EditUser(MethodView):
    """
    Edit or delete an existing user
    """

    decorators = [
        jwt_required(),
    ]

    @jwt_login_required()
    def post(self, upk: int) -> flask.Response:
        """
        Modifies a user
        """
        user: User | None = User.get(pk=upk)
        if user is None:
            return jsonify_no_content(404)
        result: AddEditUserResponse = {
            'errors': [],
            'success': False,
        }
        if not jwt_current_user.is_admin and user.pk != jwt_current_user.pk:
            result["errors"].append('Only an admin user can modify other users')
            return jsonify(result)
        js = flask.request.json
        if jwt_current_user.is_admin:
            user.username = js['username']
            user.must_change = js['mustChange']
        user.email = js['email']
        if js.get('password') is not None and js.get('password') != "":
            if js['password'] != js['confirmPassword']:
                result['errors'].append('Passwords do not match')
            else:
                user.set_password(js['password'])
        if jwt_current_user.is_admin:
            groups: list[Group] = []
            for group in Group.names():
                field_name = f'{group.lower()}Group'
                if js.get(field_name, False):
                    groups.append(group)
            user.set_groups(groups)
        if not result['errors']:
            result['success'] = True
            result['user'] = user.summary()
            db.session.commit()
        return jsonify(result)

    @jwt_login_required(admin=True)
    def delete(self, upk: int) -> flask.Response:
        """
        Deletes a user
        """
        if jwt_current_user.pk == upk:
            return jsonify({
                'error': 'You cannot delete your own account'
            }, 400)
        user: User | None = User.get(pk=upk)
        if user is None:
            return jsonify_no_content(404)
        db.session.delete(user)
        db.session.commit()
        return jsonify_no_content(204)


class EditSelf(EditUser):
    decorators = [login_required(admin=False)]

    def get_model(self) -> User:
        return current_user


def generate_csrf_tokens() -> CsrfTokenCollection:
    csrf_key: str = CsrfProtection.generate_cookie()
    if current_user.has_permission(Group.MEDIA):
        return CsrfTokenCollection(
            streams=CsrfProtection.generate_token('streams', csrf_key),
            files=CsrfProtection.generate_token('files', csrf_key),
            kids=CsrfProtection.generate_token('kids', csrf_key),
            upload=CsrfProtection.generate_token('upload', csrf_key))
    return CsrfTokenCollection(
        streams=CsrfProtection.generate_token('streams', csrf_key),
        files=None,
        kids=None,
        upload=None)


class RefreshAccessToken(MethodView):
    decorators = [
        jwt_required(refresh=True, optional=True),
    ]

    def get(self) -> flask.Response:
        user: User | None = get_current_user()
        if user is None:
            user = User.get_guest_user()
        assert user is not None
        access_token: EncodedJWTokenJson = Token.generate_api_token(user, TokenType.ACCESS)
        return jsonify({
            'accessToken': access_token,
            'csrfTokens': generate_csrf_tokens().to_dict(),
        })


class RefreshCsrfTokens(MethodView):
    decorators = [
        jwt_required(),
    ]

    def get(self) -> flask.Response:
        return jsonify({
            'csrfTokens': generate_csrf_tokens().to_dict(),
        })
