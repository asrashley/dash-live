#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import TypedDict

from flask_login import current_user

from dashlive.server.models.token import DecodedJwtToken, Token, TokenType
from dashlive.server.models.user import User

from .csrf import CsrfProtection, CsrfTokenCollection, CsrfTokenCollectionJson
from .navbar import create_navbar_context, NavBarItem

class InitialTokensType(TypedDict):
    csrfTokens: CsrfTokenCollectionJson
    accessToken: DecodedJwtToken | None
    refreshToken: DecodedJwtToken | None


class UserContextType(TypedDict):
    isAuthenticated: bool
    pk: int
    username: str
    groups: list[str]


class SpaTemplateContext(TypedDict):
    navbar: list[NavBarItem]
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
        'accessToken': access_token.to_decoded_jwt(),
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
        initial_tokens['refreshToken'] = refresh_token.to_decoded_jwt()
    navbar: list[NavBarItem] = create_navbar_context(with_login=False)
    context: SpaTemplateContext = {
        "navbar": navbar,
        "initialTokens": initial_tokens,
        "user": user_context,
    }
    return context
