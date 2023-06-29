from functools import wraps
from typing import cast, Optional

import flask  # type: ignore
from flask_login import current_user
from werkzeug.local import LocalProxy  # type: ignore

from dashlive.server.models import MediaFile, Stream

AJAX_CONTENT_TYPES = {r'application/json', r'text/javascript'}

def is_ajax() -> bool:
    # print('content_type', flask.request.content_type, flask.request.url)
    return (
        flask.request.content_type in AJAX_CONTENT_TYPES or
        flask.request.form.get("ajax", "0") == "1" or
        flask.request.args.get("ajax", "0") == "1")

def needs_login_response(admin: bool, html: bool) -> flask.Response:
    if is_ajax():
        response = flask.json.jsonify('Not Authorized')
        response.status = 401
        return response
    if html:
        return flask.render_template('needs_login.html', needs_admin=admin)
    return flask.make_response('Not Authorized', 401)

def login_required(html=False, admin=False):
    """
    Decorator that requires user to be logged in
    """
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return needs_login_response(admin=admin, html=html)
            if admin and not current_user.is_admin:
                return needs_login_response(admin=admin, html=html)
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
        mf: Optional[MediaFile] = None
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
        stream: Optional[Stream] = None
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
