#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from functools import wraps
import html
import logging
from pathlib import Path
from typing import cast, Callable, Iterable

import flask  # type: ignore
from flask_login import current_user
from flask_jwt_extended import current_user as jwt_current_user
from werkzeug.local import LocalProxy  # type: ignore

from dashlive.mpeg.dash.profiles import primary_profiles
from dashlive.server.manifests import DashManifest, manifest_map
from dashlive.server.models import (
    Group,
    Key,
    MediaFile,
    MultiPeriodStream,
    Stream,
    User
)

from .csrf import CsrfProtection
from .exceptions import CsrfFailureException
from .utils import is_ajax, jsonify, jsonify_no_content

def needs_login_response(admin: bool, html: bool, permission: Group | None) -> flask.Response:
    if is_ajax():
        response = flask.json.jsonify('Not Authorized')
        response.status = 401
        return response
    if html:
        return flask.render_template('needs_login.html', needs_admin=admin, permission=permission)
    return flask.make_response('Not Authorized', 401)

def login_required(html=False, admin=False, permission: Group | None = None):
    """
    Decorator that requires user to be logged in
    """
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return needs_login_response(admin=admin, html=html, permission=permission)
            if admin and not current_user.is_admin:
                return needs_login_response(admin=admin, html=html, permission=permission)
            if permission and not current_user.has_permission(permission):
                return needs_login_response(admin=admin, html=html, permission=permission)
            return func(*args, **kwargs)
        return decorated_function
    return decorator

def jwt_login_required(admin=False, permission: Group | None = None):
    """
    Decorator that requires an AccessToken from a logged in user
    """
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs) -> flask.Response:
            if not jwt_current_user.is_authenticated:
                return jsonify_no_content(401)
            if admin and not jwt_current_user.is_admin:
                return jsonify_no_content(401)
            if permission and not jwt_current_user.has_permission(permission):
                return jsonify_no_content(401)
            return func(*args, **kwargs)
        return decorated_function
    return decorator

def csrf_token_required(
        service: str,
        next_url: Callable[..., str | None] = lambda: None,
        optional: bool = False):
    """
    Decorator that requires a CSRF token check to pass
    """
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            token: str | None = None
            has_payload: bool = flask.request.method in {'POST', 'PUT'}
            try:
                if has_payload and flask.request.is_json:
                    token = flask.request.get_json().get('csrf_token', None)
                if token is None:
                    token = flask.request.args.get('csrf_token')
                if token is None and has_payload:
                    token = flask.request.form.get('csrf_token')
                if token is None and optional:
                    return func(*args, **kwargs)
                if token is None:
                    raise CsrfFailureException('Failed to find csrf_token')
                CsrfProtection.check(service, token)
            except (ValueError, CsrfFailureException) as err:
                logging.info('CSRF failure: %s', err)
                if is_ajax():
                    return jsonify({'error': 'CSRF failure'}, 401)
                flask.flash(f'CSRF error: {err}', 'error')
                url: str | None = next_url(*args, **kwargs)
                if url is None:
                    return flask.make_response('Not Authorized', 401)
                return flask.redirect(url)
            return func(*args, **kwargs)
        return decorated_function
    return decorator

def uses_media_file(func):
    """
    Decorator that fetches MediaFile from database.
    It will automatically return a 404 error if not found
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        filename = kwargs.get('filename', None)
        mf: MediaFile | None = None
        if filename:
            sdir = kwargs.get('stream', None)
            # print('uses_media_file', sdir, filename)
            if not sdir:
                # print(f'MediaFile {filename} not found')
                return flask.make_response(f'MediaFile {filename} not found', 404)
            stream = Stream.get(directory=sdir)
            if not stream:
                # print(f'Stream {sdir} not found')
                return flask.make_response(f'Stream {sdir} not found', 404)
            mf = MediaFile.get(stream_pk=stream.pk, name=filename.lower())
            if not mf:
                mf = MediaFile.get(stream_pk=stream.pk, name=f'{filename.lower()}.mp4')
            if not mf:
                # print(f'MediaFile {sdir}/{filename} not found')
                return flask.make_response(f'MediaFile {sdir}/{filename} not found', 404)
        if mf is None:
            mfid = kwargs.get('mfid', None)
            if not mfid:
                # print('MediaFile ID missing')
                return flask.make_response('MediaFile ID missing', 400)
            mf = MediaFile.get(pk=mfid)
            if not mf:
                # print(f'MediaFile {mfid} not found')
                return flask.make_response(f'MediaFile {mfid} not found', 404)
        flask.g.mediafile = mf
        return func(*args, **kwargs)
    return decorated_function


current_media_file = cast(MediaFile, LocalProxy(lambda: flask.g.mediafile))

def uses_stream(func):
    """
    Decorator that fetches Stream from database.
    It will automatically return a 404 error if not found
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        stream: Stream | None = None
        spk = kwargs.get('spk', None)
        if spk:
            stream = Stream.get(pk=spk)
        else:
            sid = kwargs.get('stream', None)
            if not sid:
                # print('Stream ID missing')
                return flask.make_response('Stream ID missing', 400)
            stream = Stream.get(directory=sid)
        if not stream:
            # print(f'Stream not found')
            return flask.make_response(f'Stream {spk} not found', 404)
        flask.g.stream = stream
        return func(*args, **kwargs)
    return decorated_function


current_stream = cast(Stream, LocalProxy(lambda: flask.g.stream))

def uses_keypair(func):
    """
    Decorator that fetches Key from database.
    It will automatically return a 404 error if not found
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        keypair: Key | None = None
        kpk = kwargs.get('kpk', None)
        if not kpk:
            return flask.make_response('Key primary key missing', 404)
        keypair = Key.get(pk=kpk)
        if not keypair:
            return flask.make_response(f'Key {kpk} not found', 404)
        flask.g.keypair = keypair
        return func(*args, **kwargs)
    return decorated_function


current_keypair = cast(Key, LocalProxy(lambda: flask.g.keypair))


def modifies_user_model(func):
    """
    Decorator that fetches User from database by its primary key.
    It is used for views that edit users, rather than for user login.
    It will automatically return a 404 error if not found
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        user: User | None = None
        upk = kwargs.get('upk', None)
        if not upk:
            return flask.make_response('User primary key missing', 404)
        user = User.get(pk=upk)
        if not user:
            return flask.make_response(f'User {upk} not found', 404)
        flask.g.modify_user = user
        return func(*args, **kwargs)
    return decorated_function


modifying_user = cast(User, LocalProxy(lambda: flask.g.modify_user))

def uses_manifest(func):
    """
    Decorator that checks manifest name is valid
    It will automatically return a 404 error if not found
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        manifest: DashManifest | None = None
        mft_name: str = kwargs.get('manifest', '')
        if not mft_name:
            return flask.make_response('Manifest name missing', 404)
        if not mft_name.endswith('.mpd'):
            mft_name = f"{mft_name}.mpd"
        try:
            manifest = manifest_map[mft_name]
        except KeyError as err:
            logging.debug('Unknown manifest: %s (%s)', mft_name, err)
        if manifest is None:
            return flask.make_response(
                f'{html.escape(mft_name)} not found', 404)
        mode: str | None = kwargs.get('mode')
        modes: Iterable[str] = primary_profiles.keys()
        if mode is not None:
            if mode.startswith('mps-'):
                mode = mode[4:]
            try:
                modes = manifest.restrictions['mode']
            except KeyError:
                pass
            if mode not in modes:
                logging.debug(
                    'Mode %s not supported with manifest %s (supported=%s)',
                    mode, mft_name, modes)
                return flask.make_response(
                    f'{html.escape(mft_name)} not found', 404)
        flask.g.manifest = manifest
        return func(*args, **kwargs)
    return decorated_function


current_manifest = cast(DashManifest, LocalProxy(lambda: flask.g.manifest))


def uses_multi_period_stream(func):
    """
    Decorator that fetches MultiPeriodStream from database.
    It will automatically return a 404 error if not found
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        stream: MultiPeriodStream | None = None
        name = kwargs.get('mps_name', None)
        if name is None:
            return flask.make_response(
                'Multi-period stream ID missing', 400)

        stream = MultiPeriodStream.get_one(name=name)
        if not stream:
            return flask.make_response(
                f'Multi-period stream {html.escape(name)} not found', 404)
        flask.g.mp_stream = stream
        return func(*args, **kwargs)
    return decorated_function


current_mps = cast(MultiPeriodStream, LocalProxy(lambda: flask.g.mp_stream))

def spa_handler(func):
    """
    Decorator for views that are implemented using a Single Page Application.
    Any non-ajax requests are responded with a single HTML page
    """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if is_ajax():
            return func(*args, **kwargs)
        static_dir: Path = Path(flask.current_app.config['STATIC_FOLDER'])
        return flask.send_from_directory(static_dir / 'html', 'index.html')
    return decorated_function
