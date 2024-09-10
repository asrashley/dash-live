#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from functools import wraps
from typing import cast

import flask  # type: ignore
from flask_login import current_user
from werkzeug.local import LocalProxy  # type: ignore

from dashlive.server.models import Group, Key, MediaFile, Stream, User
from .utils import is_ajax

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
