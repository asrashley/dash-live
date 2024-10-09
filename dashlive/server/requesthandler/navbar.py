#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from typing import TypedDict

import flask
from flask_login import current_user

class NavBarItem(TypedDict):
    title: str
    href: str
    active: bool

def create_navbar_context() -> list[NavBarItem]:
    navbar: list[NavBarItem] = [{
        'title': 'Home', 'href': flask.url_for('home')
    }, {
        'title': 'Streams', 'href': flask.url_for('list-streams')
    }, {
        'title': 'Multi-Period', 'href': flask.url_for('list-mps')
    }, {
        'title': 'Validate', 'href': flask.url_for('validate-stream')
    }]
    if current_user.is_authenticated:
        if current_user.is_admin:
            navbar.append({
                'title': 'Users', 'href': flask.url_for('list-users')
            })
        else:
            navbar.append({
                'title': 'My Account', 'href': flask.url_for('change-password')
            })
        navbar.append({
            'title': 'Log Out',
            'class': 'user-login',
            'href': flask.url_for('logout')
        })
    else:
        navbar.append({
            'title': 'Log In',
            'class': 'user-login',
            'href': flask.url_for('login')
        })
    found_active = False
    for nav in navbar[1:]:
        if flask.request.path.startswith(nav['href']):
            nav['active'] = True
            found_active = True
            break
    if not found_active:
        navbar[0]['active'] = True
    return navbar
