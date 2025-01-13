#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import datetime
import logging
from typing import NotRequired, TypedDict

import flask
from flask_jwt_extended import jwt_required
from flask_login import current_user, login_user, logout_user
from flask.views import MethodView

from dashlive.server import models
from dashlive.server.requesthandler.csrf import CsrfProtection, CsrfTokenCollection
from dashlive.utils.json_object import JsonObject

from .base import HTMLHandlerBase, DeleteModelBase
from .decorators import login_required, modifies_user_model, modifying_user, spa_handler
from .exceptions import CsrfFailureException
from .utils import is_ajax, jsonify

def decorate_user(user: models.User) -> JsonObject:
    js = user.to_dict()
    js['groups'] = {}
    for grp in models.Group:
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

    decorators = [spa_handler]

    def post(self) -> flask.Response:
        if not is_ajax():
            return flask.redirect(flask.url_for('home'))
        data: JsonObject = flask.request.json
        # try:
        #     self.check_csrf('login', data)
        # except (ValueError, CsrfFailureException) as err:
        #     return jsonify({'error': str(err)}, 400)
        username: str | None = data.get("username", None)
        password: str | None = data.get("password", None)
        rememberme = data.get("rememberme", False)
        user = models.User.get_one(username=username)
        if not user:
            user: models.User | None = models.User.get_one(email=username)
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
        models.db.session.commit()
        csrf_key = self.generate_csrf_cookie()
        access_token: models.Token = models.Token.generate_api_token(user, models.TokenType.ACCESS)
        refresh_token: models.Token = models.Token.generate_api_token(current_user, models.TokenType.REFRESH)
        result: LoginResponseJson = {
            'success': True,
            'mustChange': user.must_change,
            'csrf_token': self.generate_csrf_token('login', csrf_key),
            'accessToken': access_token.to_dict(only={'expires', 'jti'}),
            'refreshToken': refresh_token.to_dict(only={'expires', 'jti'}),
            'user': user.to_dict(only={'email', 'username', 'pk', 'last_login'})
        }
        result['user']['groups'] = user.get_groups()
        return jsonify(result)


class LogoutPage(HTMLHandlerBase):
    """
    Logs user out of site
    """
    def get(self) -> flask.Response:
        logout_user()
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
                decorate_user(u) for u in models.User.all()],
            'field_names': models.User.get_column_names(
                exclude={'password', 'groups_mask', 'tokens',
                         'reset_token', 'reset_expires'}),
            'group_names': models.Group.names(),
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
            'group_names': models.Group.names(),
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
            if models.User.count(username=user.username) > 0:
                return self.get(upk, error=f'User {user.username} already exists', **flask.request.form)
            if models.User.count(email=user.email) > 0:
                return self.get(
                    upk, error=f'User with email address {user.email} already exists',
                    **flask.request.form)
        if flask.request.form['password']:
            if flask.request.form['password'] != flask.request.form['confirm_password']:
                return self.get(upk, error='Passwords do not match', **flask.request.form)
            user.set_password(flask.request.form['password'])
        groups: list[models.Group] = []
        for group in models.Group.names():
            field_name = f'{group.lower()}_group'
            if flask.request.form.get(field_name, '').lower() in {'on', '1', 'checked'}:
                groups.append(models.Group[group.upper()])
        user.set_groups(groups)
        if flask.request.form['new_item'] == '1':
            user.add(commit=True)
            flask.flash(f'Added new user "{user.username}"', 'success')
        else:
            models.db.session.commit()
            flask.flash(f'Saved changes to "{user.username}"', 'success')
        if not current_user.is_admin:
            return flask.redirect(flask.url_for('home'))
        return flask.redirect(flask.url_for('list-users'))

    def get_model(self) -> models.User:
        return modifying_user


class AddUser(EditUser):
    """
    Add a new user
    """
    decorators = [login_required(admin=True)]

    def get_model(self) -> models.User:
        return models.User(groups_mask=models.Group.USER.value)


class EditSelf(EditUser):
    decorators = [login_required(admin=False)]

    def get_model(self) -> models.User:
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
        models.db.session.delete(modifying_user)
        models.db.session.commit()
        return result

    def get_next_url(self) -> str:
        return flask.url_for('list-users')


def generate_csrf_tokens() -> CsrfTokenCollection:
    csrf_key: str = CsrfProtection.generate_cookie()
    if current_user.has_permission(models.Group.MEDIA):
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
        access_token: models.Token = models.Token.generate_api_token(
            current_user, models.TokenType.ACCESS)
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
