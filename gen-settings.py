#!/usr/bin/python3

import random
import string
import os

TEMPLATE="""
FLASK_SECRET_KEY='{cookie}'
FLASK_DASH__CSRF_SECRET='{csrf}'
FLASK_DASH__DEFAULT_ADMIN_USERNAME='admin'
FLASK_DASH__DEFAULT_ADMIN_PASSWORD='{password}'
FLASK_DASH__ALLOWED_DOMAINS='*'
"""

def make_random_string(length: int) -> str:
    chars = string.ascii_letters + string.digits + r'!#$%&()+,-./:<=>?@[\]^_`{|}~'
    rv = []
    for i in range(length):
        rv.append(random.choice(chars))
    return ''.join(rv)

cookie = make_random_string(20)
csrf = make_random_string(20)
password = make_random_string(10)

if not os.path.exists(".env"):
    print(f'Creating .env with default admin account username="admin" password ="{password}"')
    with open('.env', 'wt', encoding='ascii') as out:
        out.write(TEMPLATE.format(**locals()))

