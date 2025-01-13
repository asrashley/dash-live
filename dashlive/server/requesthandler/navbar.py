#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dataclasses import dataclass
import flask
from flask_login import current_user

from dashlive.utils.json_object import JsonObject

@dataclass(kw_only=True, slots=True)
class NavBarItem:
    title: str
    href: str | None = None
    active: bool = False
    className: str = ''

    def __post_init__(self) -> None:
        if not self.active and self.href is None:
            raise ValueError('href is required for a non-active NavBarItem')

    def to_json(self) -> JsonObject:
        return {
            "title": self.title,
            "href": self.href,
            "active": self.active,
            "className": self.className,
        }


def create_navbar_context(with_login: bool = True) -> list[NavBarItem]:
    navbar: list[NavBarItem] = [
        NavBarItem(title='Home', href=flask.url_for('ui-home'), className='spa'),
        NavBarItem(title='Streams', href=flask.url_for('list-streams')),
        NavBarItem(title='Multi-Period', href=flask.url_for('ui-list-mps'),
                   className='spa'),
        NavBarItem(title='Validate', href=flask.url_for('validate-stream')),
        NavBarItem(title='Inspect', href=flask.url_for('inspect-media')),
    ]
    if current_user.is_authenticated:
        if current_user.is_admin:
            navbar.append(
                NavBarItem(title='Users', href=flask.url_for('list-users')))
        else:
            navbar.append(
                NavBarItem(title='My Account', href=flask.url_for('change-password')))
        if with_login:
            navbar.append(
                NavBarItem(
                    title='Log Out', className='user-login', href=flask.url_for('logout')))
    elif with_login:
        navbar.append(
            NavBarItem(
                title='Log In', className='user-login spa', href=flask.url_for('ui-login')))
    found_active = False
    for nav in navbar[1:]:
        if flask.request.path.startswith(nav.href):
            nav.active = True
            found_active = True
            break
    if not found_active:
        navbar[0].active = True
    return navbar
