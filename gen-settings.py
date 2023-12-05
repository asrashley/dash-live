#!/usr/bin/python3

import random
import string
import os
import sys

TEMPLATE="""
FLASK_SECRET_KEY='{cookie}'
FLASK_PREFERRED_URL_SCHEME='https'
FLASK_DASH__CSRF_SECRET='{csrf}'
FLASK_DASH__DEFAULT_ADMIN_USERNAME='admin'
FLASK_DASH__DEFAULT_ADMIN_PASSWORD='{password}'
FLASK_DASH__ALLOWED_DOMAINS='*'
FLASK_DASH__STRICT_CSRF_ORIGIN='False'
"""

def make_random_string(length: int) -> str:
    chars = string.ascii_letters + string.digits + r'!#$%&()+,-./:<=>?@[\]^_`{|}~'
    rv = []
    for i in range(length):
        rv.append(random.choice(chars))
    return ''.join(rv)

cookie = make_random_string(20)
csrf = make_random_string(20)
if len(sys.argv) > 1:
    password = sys.argv[1]
else:
    password = make_random_string(10)

if not os.path.exists(".env"):
    print(f'Creating .env with default admin account username="admin" password ="{password}"')
    with open('.env', 'w', encoding='ascii') as out:
        out.write(TEMPLATE.format(**locals()))

