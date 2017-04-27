#!/usr/bin/python
import logging, os, sys
import unittest

SDK_PATH = os.environ['LOCALAPPDATA']
#try:
#    SDK_PATH = os.environ['ProgramFiles(x86)']
#except KeyError:
#    SDK_PATH = os.environ['ProgramFiles']
SDK_PATH = os.path.join(SDK_PATH,'Google','Cloud SDK','google-cloud-sdk','platform','google_appengine')

def main(sdk_path, test_path):
    sys.path.insert(0, sdk_path)
    # path to webtest.py
    sys.path.insert(1, os.path.join(sdk_path,'lib','cherrypy'))
    import dev_appserver
    dev_appserver.fix_sys_path()
    FORMAT = "%(filename)s:%(lineno)d %(message)s"
    logging.basicConfig(format=FORMAT)
    logging.getLogger().setLevel(logging.DEBUG)
    suite = unittest.loader.TestLoader().discover(test_path)
    unittest.TextTestRunner(verbosity=2).run(suite)

#nosetests -v --with-gae --gae-lib-root="c:\Program Files (x86)\Google\google_appengine"

if __name__ == '__main__':
    TEST_PATH = '.'
    main(SDK_PATH, TEST_PATH)