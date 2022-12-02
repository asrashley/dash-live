import random
import os

TEMPLATE="""from server.gae import on_production_server

cookie_secret = r'{cookie}'
csrf_secret = r'{csrf}'
DEBUG = not on_production_server
allowed_domains = "*"
"""

cookie = []
csrf = []
chars = map(chr, range(ord('0'), ord('Z')) + range(ord('a'), ord('z')))
for i in range(20):
    cookie.append(random.choice(chars))
    csrf.append(random.choice(chars))

cookie = ''.join(cookie)
csrf = ''.join(csrf)

if not os.path.exists("src/server/settings.py"):
    with open('src/server/settings.py', 'wt') as out:
        out.write(TEMPLATE.format(**locals()))

