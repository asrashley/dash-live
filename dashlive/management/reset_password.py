#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import argparse
import sys

from dashlive.server.app import create_app
from dashlive.server.models.db import db
from dashlive.server.models.user import User

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description='Reset user password')
    ap.add_argument('--user', help='User name', default='admin')
    ap.add_argument('password', help='New password')
    args = ap.parse_args(argv[1:])

    app = create_app(create_default_user=False, wss=False)

    with app.app_context():
        user = User.get(username=args.user)
        if user is None:
            print(f'Unknown user: "{args.user}"')
            return 1
        print(f'Setting password for user {args.user}')
        user.set_password(args.password)
        user.must_change = True
        db.session.commit()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
