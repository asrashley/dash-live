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

from __future__ import print_function
from __future__ import absolute_import
import logging
import os
import subprocess
import sys
import unittest

def fixup_test_filename(name: str) -> str:
    _, tail = os.path.split(name)
    root, _ = os.path.splitext(tail)
    return root

FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.ERROR)

#if len(sys.argv) > 2:
#    os.environ["TESTS"] = ','.join(sys.argv[2:])
#    runner.main(gae_sdk, "tests", fixup_test_filename(sys.argv[1]))
#elif len(sys.argv) > 1:
#    runner.main(gae_sdk, "tests", fixup_test_filename(sys.argv[1]))
#else:
#    runner.main(gae_sdk, "tests", "*_test.py")

if __name__ == "__main__":
    argv = [fixup_test_filename(arg) for arg in sys.argv]
    print(argv)
    if len(argv) == 1:
        unittest.main(module='tests')
    else:
        unittest.main(module='tests', argv=argv)
