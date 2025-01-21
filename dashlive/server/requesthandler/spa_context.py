#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from typing import TypedDict

from dashlive.server.models.token import EncodedJWTokenJson, Token, TokenType
from dashlive.server.models.user import User

from .csrf import CsrfProtection, CsrfTokenCollection, CsrfTokenCollectionJson
from .navbar import create_navbar_context, NavBarItem

class InitialTokensType(TypedDict):
    csrfTokens: CsrfTokenCollectionJson
    accessToken: EncodedJWTokenJson | None


class SpaTemplateContext(TypedDict):
    navbar: list[NavBarItem]
    initialTokens: InitialTokensType


def create_spa_template_context(user: User) -> SpaTemplateContext:
    csrf_key: str = CsrfProtection.generate_cookie()
    csrf_tokens = CsrfTokenCollection(
        streams=CsrfProtection.generate_token('streams', csrf_key),
        files=None,
        kids=None,
        upload=None)
    access_token: EncodedJWTokenJson = Token.generate_api_token(user, TokenType.ACCESS).toJSON()
    initial_tokens: InitialTokensType = {
        'csrfTokens': csrf_tokens.to_dict(),
        'accessToken': access_token,
    }
    navbar: list[NavBarItem] = create_navbar_context(with_login=False)
    context: SpaTemplateContext = {
        "navbar": navbar,
        "initialTokens": initial_tokens,
    }
    return context
