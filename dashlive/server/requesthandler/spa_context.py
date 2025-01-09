#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import Any, TypedDict, cast

import flask
from flask_login import current_user

from dashlive.server.models.token import Token, TokenType
from dashlive.server.models.user import User
from dashlive.server.routes import routes, Route

from .csrf import CsrfProtection, CsrfTokenCollection, CsrfTokenCollectionJson
from .navbar import create_navbar_context, NavBarItem
from .template_context import create_template_context, TemplateContext

class JwtToken(TypedDict):
    jti: str
    expired: str


class InitialTokensType(TypedDict):
    csrfTokens: CsrfTokenCollectionJson
    accessToken: JwtToken | None
    refreshToken: JwtToken | None


class UserContextType(TypedDict):
    isAuthenticated: bool
    pk: int
    username: str
    groups: list[str]


class SpaTemplateContext(TemplateContext):
    force_es5: bool
    navbar: list[NavBarItem]
    routes: dict[str, Route]
    breadcrumbs: list[NavBarItem]
    initialTokens: InitialTokensType
    user: UserContextType


def create_spa_template_context() -> SpaTemplateContext:
    csrf_key: str = CsrfProtection.generate_cookie()
    csrf_tokens = CsrfTokenCollection(
        streams=CsrfProtection.generate_token('streams', csrf_key),
        files=None,
        kids=None,
        upload=None)
    user: User = current_user
    if not current_user.is_authenticated:
        user = User.get_guest_user()
    access_token: Token = Token.generate_api_token(user, TokenType.ACCESS)
    initial_tokens: InitialTokensType = {
        'csrfTokens': csrf_tokens.to_dict(),
        'accessToken': access_token.to_dict(only={'expires', 'jti'}),
        'refreshToken': None,
    }
    user_context: UserContextType = {
        'isAuthenticated': current_user.is_authenticated,
        'pk': user.pk,
        'username': user.username,
        'groups': user.get_groups(),
    }
    if current_user.is_authenticated:
        refresh_token: Token = Token.generate_api_token(
            current_user, TokenType.REFRESH)
        initial_tokens['refreshToken'] = refresh_token.to_dict(
            only={'expires', 'jti'})
    navbar: list[NavBarItem] = create_navbar_context()
    breadcrumbs: list[NavBarItem] = [
        NavBarItem(title='Home', active=True)
    ]
    context: SpaTemplateContext = cast(SpaTemplateContext, create_template_context(
        title='DASH Test Streams',
        navbar=navbar, routes=routes, breadcrumbs=breadcrumbs,
        initialTokens=initial_tokens, user=user_context,
        force_es5=('es5' in flask.request.args)))
    return context
