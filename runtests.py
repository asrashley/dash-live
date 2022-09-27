#!/usr/bin/env python

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

import logging
import os
import subprocess
import sys
import unittest

if not os.path.exists("runner.py"):
    rv = subprocess.call([
        'wget', 'https://raw.githubusercontent.com/GoogleCloudPlatform/python-docs-samples/6f5f3bcb81779679a24e0964a6c57c0c7deabfac/appengine/standard/localtesting/runner.py'
    ])
    if rv:
        print 'Failed to download runner.py'
        sys.exit(1)

import runner

def fixup_test_filename(name):
    _, tail = os.path.split(name)
    root, ext = os.path.splitext(tail)
    if not ext:
        ext = '.py'
    return root + ext

try:
    # On Windows, assume GAE SDK is installed in user's local app data directory
    appdata = os.environ['LOCALAPPDATA']
    gae_sdk = os.path.join(appdata,'Google','Cloud SDK','google-cloud-sdk','platform','google_appengine')
except KeyError:
    # On Unix, assume dev_appserver.py is in the PATH
    dev_appserver = subprocess.check_output(["which", "dev_appserver.py"]).split('\n')[0]
    dev_appserver = os.path.abspath(os.path.realpath(dev_appserver))
    gae_sdk = os.path.dirname(dev_appserver)
    # in some installations, dev_appserver.py is in the root of the GAE SDK folder
    # in others, it is in a "bin" sub-directory
    if gae_sdk.endswith("bin"):
        gae_sdk = os.path.dirname(gae_sdk)

FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.ERROR)
        
if len(sys.argv) > 2:
    os.environ["TESTS"] = ','.join(sys.argv[2:])
    runner.main(gae_sdk, "tests", fixup_test_filename(sys.argv[1]))
elif len(sys.argv) > 1:
    runner.main(gae_sdk, "tests", fixup_test_filename(sys.argv[1]))
else:
    runner.main(gae_sdk, "tests", "*_test.py")
