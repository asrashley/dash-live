#!/usr/bin/python3

import argparse
import random
import secrets
import string
import os
import sys

TEMPLATE="""
FLASK_SECRET_KEY='{cookie}'
FLASK_DASH__CSRF_SECRET='{csrf}'
FLASK_DASH__DEFAULT_ADMIN_USERNAME='admin'
FLASK_DASH__DEFAULT_ADMIN_PASSWORD='{password}'
FLASK_DASH__ALLOWED_DOMAINS='*'
FLASK_DASH__STRICT_CSRF_ORIGIN='False'
FLASK_DASH__PROXY_DEPTH='{proxy_depth}'
JWT_SECRET_KEY='{jwt_key}'
"""

def make_random_string(length: int) -> str:
    chars = string.ascii_letters + string.digits + r'!#$%&()+,-./:<=>?@[\]^_`{|}~'
    rv = []
    for i in range(length):
        rv.append(random.choice(chars))
    return ''.join(rv)

parser = argparse.ArgumentParser(description='Generate dash-live server settings')
parser.add_argument(
    '--proxy-depth', type=int, dest='proxy_depth', default=0,
    help='Number of proxy servers to trust when checking X-Forwarded- headers')
parser.add_argument('--password', help='Default admin password', default=make_random_string(10))
args = parser.parse_args()

if not os.path.exists(".env"):
    cookie = make_random_string(20)
    csrf = make_random_string(20)
    jwt_key = secrets.token_urlsafe(24)
    print(f'Creating .env with default admin account username="admin" password="{args.password}"')
    with open('.env', 'w', encoding='ascii') as out:
        out.write(TEMPLATE.format(
            cookie=cookie, csrf=csrf, password=args.password,
            proxy_depth=args.proxy_depth, jwt_key=jwt_key))

