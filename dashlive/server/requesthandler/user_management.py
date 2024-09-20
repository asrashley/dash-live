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

import datetime

import flask
from flask_login import current_user, login_user, logout_user

from dashlive.server import models
from dashlive.utils.json_object import JsonObject

from .base import HTMLHandlerBase, DeleteModelBase
from .decorators import login_required, modifies_user_model, modifying_user
from .exceptions import CsrfFailureException
from .utils import is_ajax, jsonify

def decorate_user(user: models.User) -> JsonObject:
    js = user.to_dict()
    js['groups'] = {}
    for grp in models.Group:
        if user.is_member_of(grp):
            js['groups'][grp.name] = True
    return js


class LoginPage(HTMLHandlerBase):
    """
    handler for logging into the site
    """

    def get(self):
        context = self.create_context()
        csrf_key = self.generate_csrf_cookie()
        context['csrf_token'] = self.generate_csrf_token('login', csrf_key)
        if is_ajax():
            return jsonify({
                'csrf_token': context['csrf_token']
            })
        return flask.render_template('users/login.html', **context)

    def post(self):
        if is_ajax():
            data = flask.request.json
            try:
                self.check_csrf('login', data)
            except (ValueError, CsrfFailureException) as err:
                return jsonify({'error': str(err)}, 400)
            username = data.get("username", None)
            password = data.get("password", None)
            rememberme = data.get("rememberme", False)
        else:
            try:
                self.check_csrf('login', flask.request.form)
            except (ValueError, CsrfFailureException) as err:
                flask.flash(f'CSRF failure: {err}', 'error')
                return self.get()
            username = flask.request.form.get("username", None)
            password = flask.request.form.get("password", None)
            rememberme = flask.request.form.get("rememberme", '') == 'on'
        user = models.User.get_one(username=username)
        if not user:
            user = models.User.get_one(email=username)
        if not user or not user.check_password(password):
            context = self.create_context()
            context['error'] = "Wrong username or password"
            csrf_key = self.generate_csrf_cookie()
            context['csrf_token'] = self.generate_csrf_token('login', csrf_key)
            context['username'] = username
            if is_ajax():
                result = {}
                for field in ['error', 'csrf_token']:
                    result[field] = context[field]
                return jsonify(result)
            return flask.render_template('users/login.html', **context)
        login_user(user, remember=rememberme)
        user.last_login = datetime.datetime.now()
        models.db.session.commit()
        if is_ajax():
            csrf_key = self.generate_csrf_cookie()
            result = {
                'success': True,
                'csrf_token': self.generate_csrf_token('login', csrf_key),
                'user': user.to_dict(only={'email', 'username', 'pk', 'last_login'})
            }
            result['user']['groups'] = user.get_groups()
            return jsonify(result)
        if user.must_change:
            flask.flash('You must change your password', 'info')
            return flask.redirect(flask.url_for('change-password'))
        next_url = flask.request.args.get('next')
        # TODO: check if next is to an allowed location
        response = flask.make_response(flask.redirect(next_url or flask.url_for('home')))
        return response


class LogoutPage(HTMLHandlerBase):
    """
    Logs user out of site
    """
    def get(self):
        logout_user()
        return flask.redirect(flask.url_for('home'))

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
            return flask.make_response({'error': f'CSRF failure: {err}'}, 400)
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
