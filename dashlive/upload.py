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
import logging
import sys

from dashlive.management.frontend_db import FrontendDatabaseAccess
from dashlive.management.populate import PopulateDatabase

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description='dashlive database population')
    ap.add_argument('--debug', action="store_true",
                    help='Display debugging information when populating database')
    ap.add_argument('--silent', action="store_true",
                    help='Only show warnings and errors')
    ap.add_argument('--host', help='HTTP address of host to populate',
                    default="http://localhost:5000/")
    ap.add_argument('--username')
    ap.add_argument('--password')
    ap.add_argument('jsonfile', help='JSON file', nargs='+', default=None)
    args = ap.parse_args(argv)
    mm_log = logging.getLogger('management')
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s: %(funcName)s:%(lineno)d: %(message)s'))
    mm_log.addHandler(ch)
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        mm_log.setLevel(logging.DEBUG)
    elif args.silent:
        mm_log.setLevel(logging.WARNING)
    else:
        mm_log.setLevel(logging.INFO)
    fda = FrontendDatabaseAccess(args.host, args.username, args.password)
    pd = PopulateDatabase(fda)
    rv: int = 0
    for jsonfile in args.jsonfile:
        if not pd.populate_database(jsonfile):
            rv = 1
    return rv


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
