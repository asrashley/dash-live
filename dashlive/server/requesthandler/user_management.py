#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime
import logging
from typing import NotRequired, TypedDict, cast

import flask
from flask_jwt_extended import get_jwt, jwt_required, current_user as jwt_current_user
from flask_login import current_user, login_user, logout_user
from flask.views import MethodView

from dashlive.server.models.db import db
from dashlive.server.models.group import Group
from dashlive.server.models.token import EncodedJWTokenJson, TokenType, Token
from dashlive.server.models.user import User
from dashlive.utils.json_object import JsonObject

from .base import HTMLHandlerBase, DeleteModelBase
from .csrf import CsrfProtection, CsrfTokenCollection
from .decorators import login_required, modifies_user_model, modifying_user
from .exceptions import CsrfFailureException
from .utils import is_ajax, jsonify, jsonify_no_content

def decorate_user(user: User) -> JsonObject:
    js = user.to_dict()
    js['groups'] = {}
    for grp in Group:
        if user.is_member_of(grp):
            js['groups'][grp.name] = True
    return js

class UserSummaryJson(TypedDict):
    email: str
    username: str
    pk: int
    last_login: str
    groups: list[str]

class LoginResponseJson(TypedDict):
    success: bool
    mustChange: NotRequired[bool]
    csrf_token: str
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
        result: LoginResponseJson = {
            'success': True,
            'mustChange': user.must_change,
            'csrf_token': self.generate_csrf_token('login', csrf_key),
            'accessToken': access_token,
            'user': user.to_dict(only={'email', 'username', 'pk', 'last_login'})
        }
        result['user']['groups'] = user.get_groups()
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

class ListUsers(HTMLHandlerBase):
    """
    List all user accounts
    """
    decorators = [login_required(admin=True)]

    def get(self) -> flask.Response:
        context = self.create_context()
        context.update({
            'users': [
                decorate_user(u) for u in User.all()],
            'field_names': User.get_column_names(
                exclude={'password', 'groups_mask', 'tokens',
                         'reset_token', 'reset_expires'}),
            'group_names': Group.names(),
        })
        return flask.render_template('users/index.html', **context)


class EditUser(HTMLHandlerBase):
    """
    Edit an existing user
    """
    decorators = [modifies_user_model, login_required(admin=True)]

    def get(self, upk: int | None = None, error: str | None = None, **kwargs) -> flask.Response:
        """
        Returns an HTML form for editing a user
        """
        context = self.create_context()
        csrf_key = self.generate_csrf_cookie()
        user = self.get_model()
        new_item = not user.pk
        if current_user.is_admin:
            cancel_url = flask.url_for('list-users')
        else:
            cancel_url = flask.url_for('home')
        context.update({
            'error': error,
            'form_id': 'add-user' if new_item else 'edit-user',
            'cancel_url': cancel_url,
            'csrf_token': self.generate_csrf_token('users', csrf_key),
            'fields': user.get_fields(
                with_confirm_password=True, with_must_change=current_user.is_admin,
                **kwargs),
            'group_names': Group.names(),
            'model': decorate_user(user),
        })
        if not current_user.is_admin:
            # a user is not allowed to modify their username
            context['fields'][0]['disabled'] = True
        context['fields'].append({
            'name': 'new_item',
            'type': 'hidden',
            'value': '1' if new_item else '0',
        })
        return flask.render_template('users/edit_user.html', **context)

    def post(self, upk: int | None = None) -> flask.Response:
        """
        Modifies a user
        """
        try:
            self.check_csrf('users', flask.request.form)
        except (ValueError, CsrfFailureException) as err:
            logging.error('CSRF failure: %s', err)
            return flask.make_response({'error': 'CSRF failure occurred'}, 400)
        user = self.get_model()
        if not current_user.is_admin and user.pk != current_user.pk:
            flask.flash('Only an admin user can modify other users', 'error')
            return flask.redirect(flask.url_for('home'))
        user.username = flask.request.form['username']
        user.email = flask.request.form['email']
        user.must_change = self.get_bool_param('must_change', False)
        if flask.request.form['new_item'] == '1':
            if not flask.request.form['password']:
                return self.get(upk, error='A password must be provided', **flask.request.form)
            if User.count(username=user.username) > 0:
                return self.get(upk, error=f'User {user.username} already exists', **flask.request.form)
            if User.count(email=user.email) > 0:
                return self.get(
                    upk, error=f'User with email address {user.email} already exists',
                    **flask.request.form)
        if flask.request.form['password']:
            if flask.request.form['password'] != flask.request.form['confirm_password']:
                return self.get(upk, error='Passwords do not match', **flask.request.form)
            user.set_password(flask.request.form['password'])
        groups: list[Group] = []
        for group in Group.names():
            field_name = f'{group.lower()}_group'
            if flask.request.form.get(field_name, '').lower() in {'on', '1', 'checked'}:
                groups.append(Group[group.upper()])
        user.set_groups(groups)
        if flask.request.form['new_item'] == '1':
            user.add(commit=True)
            flask.flash(f'Added new user "{user.username}"', 'success')
        else:
            db.session.commit()
            flask.flash(f'Saved changes to "{user.username}"', 'success')
        if not current_user.is_admin:
            return flask.redirect(flask.url_for('home'))
        return flask.redirect(flask.url_for('list-users'))

    def get_model(self) -> User:
        return modifying_user


class AddUser(EditUser):
    """
    Add a new user
    """
    decorators = [login_required(admin=True)]

    def get_model(self) -> User:
        return User(groups_mask=Group.USER.value)


class EditSelf(EditUser):
    decorators = [login_required(admin=False)]

    def get_model(self) -> User:
        return current_user


class DeleteUser(DeleteModelBase):
    """
    Confirms and deletes a User
    """

    MODEL_NAME = 'user'
    CSRF_TOKEN_NAME = 'users'
    decorators = [modifies_user_model, login_required(html=True, admin=True)]

    def get_model_dict(self) -> JsonObject:
        js = modifying_user.to_dict()
        js['title'] = js['username']
        return js

    def get_cancel_url(self) -> str:
        return flask.url_for('list-users')

    def delete_model(self) -> JsonObject:
        if current_user.pk == modifying_user.pk:
            if not is_ajax():
                flask.flash('You cannot delete your own account', 'error')
            return {
                'error': 'You cannot delete your own account'
            }
        result = {
            "deleted": modifying_user.pk,
            "username": modifying_user.username,
            "email": modifying_user.email
        }
        db.session.delete(modifying_user)
        db.session.commit()
        return result

    def get_next_url(self) -> str:
        return flask.url_for('list-users')


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
        login_required(),
        jwt_required(refresh=True),
    ]

    def get(self) -> flask.Response:
        access_token: EncodedJWTokenJson = Token.generate_api_token(
            current_user, TokenType.ACCESS)
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
