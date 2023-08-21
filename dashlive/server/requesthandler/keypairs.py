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

import flask

from dashlive.drm.playready import PlayReady
from dashlive.drm.keymaterial import KeyMaterial
from dashlive.server import models

from .base import RequestHandlerBase
from .decorators import login_required, uses_keypair, current_keypair
from .exceptions import CsrfFailureException

class KeyHandler(RequestHandlerBase):
    """
    Handler to add, edit and remove encryption keys
    """
    decorators = [login_required(permission=models.Group.MEDIA)]

    def get(self, kpk: int | None = None) -> flask.Response:
        """
        Returns an HTML form for adding or editing a key
        """
        context = self.create_context()
        csrf_key = self.generate_csrf_cookie()
        model: models.Key | None = None
        new_key = False
        if kpk:
            model = models.Key.get(pk=kpk)
        if model is None:
            model = models.Key(computed=True)
            new_key = True
        cancel_url = self.get_next_url_with_fallback('list-streams')
        submit_url = flask.url_for(
            flask.request.endpoint, kpk=kpk, next=self.get_next_url())
        context.update({
            'csrf_token': self.generate_csrf_token('keys', csrf_key),
            'cancel_url': cancel_url,
            'submit_url': submit_url,
            'model': model.to_dict(),
            "fields": model.get_fields()
        })
        for field in context['fields']:
            name = field['name']
            if name == 'hkid' and not new_key:
                field['disabled'] = True
                continue
            if name in flask.request.args:
                field['value'] = flask.request.args[name]
            elif name in flask.request.form:
                field['value'] = flask.request.form[name]
        context['fields'].append({
            "name": "new_key",
            "title": "Adding a new key",
            "type": "hidden",
            "value": '1' if new_key else '0',
        })
        return flask.render_template('media/edit_key.html', **context)

    def post(self, kpk: int | None = None) -> flask.Response:
        """
        Saves changes submitted by HTML form
        """
        try:
            self.check_csrf('keys', flask.request.form)
        except (ValueError, CsrfFailureException) as err:
            return flask.make_response((f'CSRF failure: {err}', 400))
        model: models.Key | None = None
        if kpk:
            model = models.Key.get(pk=kpk)
            if model is None:
                return flask.response(f'Unknown key {kpk}', 404)

        if model is None:
            model = models.Key()
        new_key = flask.request.form['new_key'] == '1'
        try:
            if new_key:
                model.hkid = KeyMaterial(hex=flask.request.form['hkid']).hex
            model.hkey = KeyMaterial(hex=flask.request.form['hkey']).hex
        except (ValueError) as err:
            flask.flash(f'Invalid values: {err}', 'error')
            return self.get(kpk)
        model.computed = flask.request.form.get('computed', 'off') == 'on'
        if new_key:
            model.add()
        models.db.session.commit()
        flask.flash(f'Saved changes to keypair {model.hkid}', 'success')
        return flask.redirect(self.get_next_url_with_fallback('list-streams'))

    def put(self, **kwargs):
        """
        handler for adding a key pair
        """
        # TODO: support JSON payload
        kid = flask.request.args.get('kid')
        key = flask.request.args.get('key')
        if kid is None:
            return self.jsonify({'error': 'KID is required'}, 400)
        result = {"error": None}
        try:
            self.check_csrf('keys', flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            result = {
                "error": f'CSRF failure: {err}'
            }
        if result['error'] is None:
            kid = models.KeyMaterial(kid)
            computed = False
            if key:
                key = models.KeyMaterial(key)
            else:
                key = models.KeyMaterial(
                    raw=PlayReady.generate_content_key(kid.raw))
                computed = True
            keypair = models.Key.get(hkid=kid.hex)
            if keypair:
                result['error'] = f"Duplicate KID {kid.hex}"
            else:
                keypair = models.Key(hkid=kid.hex, hkey=key.hex, computed=computed)
                keypair.add(commit=True)
                result = {
                    "key": key.hex,
                    "kid": kid.hex,
                    "computed": computed
                }
        csrf_key = self.generate_csrf_cookie()
        result["csrf_token"] = self.generate_csrf_token('keys', csrf_key)
        return self.jsonify(result)


class DeleteKeyHandler(RequestHandlerBase):
    """
    Handler used by HTML pages to delete encryption keys
    """
    decorators = [uses_keypair, login_required(permission=models.Group.MEDIA)]

    def get(self, kpk: int) -> flask.Response:
        """
        Returns HTML form to confirm deletion of key pair
        """
        csrf_key = self.generate_csrf_cookie()
        if self.is_ajax():
            return self.jsonify({
                'model': current_keypair.to_dict(),
                'csrf_token': self.generate_csrf_token('keys', csrf_key),
            })
        context = self.create_context()
        cancel_url = self.get_next_url_with_fallback('edit-key', kpk=current_keypair.pk)
        context.update({
            'model': current_keypair.to_dict(),
            'cancel_url': cancel_url,
            'submit_url': flask.request.url,
            'csrf_token': self.generate_csrf_token('keys', csrf_key),
        })
        context['model']['title'] = f'Keypair {current_keypair.hkid}'
        return flask.render_template('delete_model_confirm.html', **context)

    def post(self, kpk: int) -> flask.Response:
        """
        Confirms key deletion by HTML form submission
        """
        try:
            self.check_csrf('keys', flask.request.form)
        except (ValueError, CsrfFailureException) as err:
            return flask.make_response(f'CSRF failure: {err}', 400)
        models.db.session.delete(current_keypair)
        models.db.session.commit()
        flask.flash(f'Deleted keypair {current_keypair.hkid}', 'success')
        return flask.redirect(flask.url_for('list-streams'))

    def delete(self, kpk: int, **kwargs) -> flask.Response:
        """
        AJAX handler for deleting a key pair
        """
        # TODO: add support for JSON payload
        try:
            self.check_csrf('keys', flask.request.args)
        except (ValueError, CsrfFailureException) as err:
            return self.jsonify({'error': f'CSRF failure: {err}'}, 400)
        result = {
            "deleted": current_keypair.KID.hex,
        }
        models.db.session.delete(current_keypair)
        models.db.session.commit()
        csrf_key = self.generate_csrf_cookie()
        result["csrf"] = self.generate_csrf_token('keys', csrf_key)
        return self.jsonify(result)
