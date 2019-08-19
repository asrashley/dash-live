import datetime, hashlib, hmac, json, re, os, unittest, uuid

#from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed
from google.appengine.api import users
from google.appengine.api.files import file_service_stub
from google.appengine.api.blobstore import blobstore_stub, file_blob_storage
import webapp2
import webtest # if this import fails, "pip install WebTest"

import models
import views
import utils
import routes
import testcases

# convert App Engine's template syntax in to the Python string format syntax
for name,r in routes.routes.iteritems():
    r.template = re.sub(r':[^>]*>','}',r.template.replace('<','{'))

class GAETestCase(unittest.TestCase):
    def _init_blobstore_stub(self):
        blob_storage = file_blob_storage.FileBlobStorage('tmp', testbed.DEFAULT_APP_ID)
        blob_stub = blobstore_stub.BlobstoreServiceStub(blob_storage)
        file_stub = file_service_stub.FileServiceStub(blob_storage)
        self.testbed._register_stub('blobstore',blob_stub)
        self.testbed._register_stub('file',file_stub)

    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_blobstore_stub()
        #self._init_blobstore_stub()
        self.testbed.init_taskqueue_stub()
        self.testbed.init_channel_stub()
        self.testbed.init_memcache_stub()
        #self.testbed.setup_env(USER_EMAIL='usermail@gmail.com',USER_ID='1', USER_IS_ADMIN='0')
        self.testbed.init_user_stub()
        self.wsgi = webapp2.WSGIApplication(routes.webapp_routes, debug=True)
        #app.router.add(Route(r'/discover/<service_type:[\w\-_\.]+>/', handler='views.SearchHandler', parent="search", title="Search by type"))
        self.app = webtest.TestApp(self.wsgi, extra_environ={ 'REMOTE_USER':'test@example.com',
                                                            'REMOTE_ADDR':'10.10.0.1', 
                                                            'HTTP_X_APPENGINE_COUNTRY':'zz',
                                                            'HTTP_USER_AGENT':'Mozilla/5.0 (GAE Unit test) Gecko/20100101 WebTest/2.0'
                                                            })
        self.auth = None
        self.uid="4d9cf5f4-4574-4381-9df3-1d6e7ca295ff"
        
    def tearDown(self):
        self.logoutCurrentUser()
        self.testbed.deactivate()
        
    def from_uri(self, name, **kwargs):
        return routes.routes[name].template.format(**kwargs)
            
    def setCurrentUser(self, email=None, user_id=None, is_admin=False):
        os.environ['USER_EMAIL'] = email or 'test@example.com'
        os.environ['USER_ID'] = user_id or 'test'
        os.environ['USER_IS_ADMIN'] = '1' if is_admin else '0'
        self.user = users.get_current_user()

    def logoutCurrentUser(self):
        self.setCurrentUser(None, None)
        
class DateTimeTests(unittest.TestCase):
    def test_isoformat(self):
        date_str = "2013-07-25T09:57:31Z"
        date_val = utils.from_isodatetime(date_str)
        self.assertEqual(date_val.year,2013)
        self.assertEqual(date_val.month, 7)
        self.assertEqual(date_val.day, 25)
        self.assertEqual(date_val.hour, 9)
        self.assertEqual(date_val.minute, 57)
        self.assertEqual(date_val.second, 31)
        # Don't check for the 'Z' because Python doesn't put the timezone in the isoformat string
        isoformat = date_val.isoformat().replace('+00:00','Z')
        self.assertEqual(isoformat,date_str)
        date_str = "2013-07-25T09:57:31.123Z"
        date_val = utils.from_isodatetime(date_str)
        self.assertEqual(date_val.microsecond, 123000)
        # Don't check for the 'Z' because Python doesn't put the timezone in the isoformat string
        self.assertTrue(date_val.isoformat().startswith(date_str[:-1]))

class TestHandlers(GAETestCase):
    def test_index(self):
        page = views.MainPage()
        self.assertIsNotNone(getattr(page,'get',None))
        url = self.from_uri('home')
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        for pagenum, tests in enumerate(testcases.test_cases):
            response = self.app.get(url+'?page={0:d}'.format(pagenum+1))
            self.assertEqual(response.status_int, 200)
            for t in tests:
                mpd_url = self.from_uri('dash-mpd',manifest=t['manifest'])
                response.mustcontain(mpd_url, no=routes.routes['upload'].title)
        #self.setCurrentUser(is_admin=False)
        #response = self.app.get(url)
        #response.mustcontain('<a href="',mpd_url, no=routes.routes['upload'].title)        
        
class BlobstoreTestHandlers(GAETestCase):
    def setUp(self):
        super(BlobstoreTestHandlers,self).setUp()
        self.wsgi.router.add(webapp2.Route(template=r'/_ah/upload/<blob_id:[\w\-_\.]+>', handler=views.UploadHandler, name="uploadBlob_ah"))
        routes.routes['uploadBlob_ah'] = routes.routes['uploadBlob']
        
    def test_upload_media_file(self):
        #'_ah/upload/agx0ZXN0YmVkLXRlc3RyGwsSFV9fQmxvYlVwbG9hZFNlc3Npb25fXxgCDA'
        url = self.from_uri('upload')
        # not logged in as admin
        blobURL = self.from_uri('uploadBlob')
        self.assertIsNotNone(blobURL)
        response = self.app.get(url, status=401)
        # not logged in, should rerturn authentication error
        self.assertEqual(response.status_int,401)
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        form = response.form
        #form = {}
        #form['submit']='submit'
        form['file'] = webtest.Upload('V1.mp4', b'data', 'video/mp4')
        #form['file']['blob-key'] = response.form.action.split('/')[-1]
        form['media'] = 'V1'
        #print(str(form.fields))
        #print form
        self.logoutCurrentUser()
        response = form.submit('submit', status=401)
        self.setCurrentUser(is_admin=True)
        response = form.submit('submit')
        #print(response)
        
if __name__ == '__main__':
    unittest.main()        