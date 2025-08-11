#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import argparse
from os import environ
import sys

from flask import Flask
from dotenv import load_dotenv

from dashlive.server.app import create_app
from dashlive.server.models.db import db
from dashlive.server.models.group import Group
from dashlive.server.models.user import User

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description='Create new database, if required')
    ap.add_argument('--user', help='Admin account user name')
    ap.add_argument('--password', help='Admin account password')
    args = ap.parse_args(argv[1:])

    load_dotenv(environ.get('DASHLIVE_SETTINGS', '.env'))

    print('Creating database, if required')
    create_default_user: bool = not args.user
    app: Flask = create_app(create_default_user=create_default_user, wss=False)

    if create_default_user:
        return 0

    with app.app_context():
        user: User | None = User.get(username=args.user)
        if user is None:
            print(f'Creating user: "{args.user}"')
            user = User(
                username=args.user,
                must_change=True,
                email=args.user,
                groups_mask=Group.ADMIN)
            if args.password:
                user.set_password(args.password)
            else:
                user.set_password(app.config['DASH']['DEFAULT_ADMIN_PASSWORD'])
            db.session.add(user)
        else:
            print(f'Setting password for user {args.user}')
            user.set_password(args.password)
            user.must_change = True
        db.session.commit()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
