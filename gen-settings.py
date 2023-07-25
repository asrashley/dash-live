#!/usr/bin/python3

import random
import string
import os

TEMPLATE="""
SECRET_KEY = r'{cookie}'
DASH = {
  CSRF_SECRET: r'{csrf}',
  default_admin_username: 'admin',
  default_admin_password: r'{password}',
  allowed_domains: "*"
}
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

if not os.path.exists("dashlive/server/settings.py"):
    print(f'Creating settings.py with default admin account username="admin" password ="{password}"')
    with open('dashlive/server/settings.py', 'wt', encoding='ascii') as out:
        out.write(TEMPLATE.format(**locals()))

