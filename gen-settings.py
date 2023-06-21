#!/usr/bin/python3

import random
import os

TEMPLATE="""from server.gae import on_production_server

cookie_secret = r'{cookie}'
csrf_secret = r'{csrf}'
jwt_secret = r'{jwt}'
default_admin_username = 'admin'
default_admin_password = r'{password}'
DEBUG = not on_production_server
allowed_domains = "*"
"""

def make_random_string(length: int) -> str:
    chars = map(chr,
                range(ord('0'), ord('Z')) +
                range(ord('a'), ord('z')))
    rv = []
    for i in range(length):
        rv.append(random.choice(chars))
    return ''.join(rv)

cookie = make_random_string(20)
csrf = make_random_string(20)
jwt = make_random_string(20)
password = make_random_string(10)

if not os.path.exists("dashlive/server/settings.py"):
    with open('dashlive/server/settings.py', 'wt') as out:
        out.write(TEMPLATE.format(**locals()))

