from __future__ import print_function

import base64
import binascii
import cookielib
import copy
import datetime
from functools import wraps
import hashlib
import hmac
import io
import json
import re
import logging
import math
import md5
import os
import unittest
try:
    from unittest import mock
except ImportError:
    # use Python 2 back-port
    import mock
import urlparse
import urllib
import uuid
import sys
from xml.etree import ElementTree

#from google.appengine.api import memcache
from google.appengine.ext import ndb, testbed
from google.appengine.api import datastore, files, users
from google.appengine.api.files import file_service_stub
from google.appengine.api.blobstore import blobstore_stub, file_blob_storage
import jinja2
import webapp2
import webtest # if this import fails, "pip install WebTest"

_src = os.path.join(os.path.dirname(__file__),"..", "src")
if not _src in sys.path:
    sys.path.append(_src)

import dash
import drm
import models
import mp4
import views
import utils
import manifests
import options
import routes
from mixins import TestCaseMixin, HideMixinsFilter
from segment import Representation

real_datetime_class = datetime.datetime

def mock_datetime_now(target):
    """Override ``datetime.datetime.now()`` with a custom target value.
    This creates a new datetime.datetime class, and alters its now()/utcnow()
    methods.
    Returns:
        A mock.patch context, can be used as a decorator or in a with.
    """
    # See http://bugs.python.org/msg68532
    # And http://docs.python.org/reference/datamodel.html#customizing-instance-and-subclass-checks
    class DatetimeSubclassMeta(type):
        """We need to customize the __instancecheck__ method for isinstance().
        This must be performed at a metaclass level.
        """
        @classmethod
        def __instancecheck__(mcs, obj):
            return isinstance(obj, real_datetime_class)

    class BaseMockedDatetime(real_datetime_class):
        @classmethod
        def now(cls, tz=None):
            return target.replace(tzinfo=tz)

        @classmethod
        def utcnow(cls):
            return target

    # Python2 & Python3-compatible metaclass
    MockedDatetime = DatetimeSubclassMeta('datetime', (BaseMockedDatetime,), {})
    return mock.patch.object(datetime, 'datetime', MockedDatetime)
        
def add_url(method, url):
    @wraps(method)
    def tst_fn(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except AssertionError:
            print(url)
            raise
    return tst_fn
                                                                                    
class GAETestCase(TestCaseMixin, unittest.TestCase):
    MEDIA_DURATION=40 # duration of media in test/fixtures directory (in seconds)

    def _init_blobstore_stub(self):
        blob_storage = file_blob_storage.FileBlobStorage('tmp', testbed.DEFAULT_APP_ID)
        blob_stub = blobstore_stub.BlobstoreServiceStub(blob_storage)
        file_stub = file_service_stub.FileServiceStub(blob_storage)
        self.testbed._register_stub('blobstore',blob_stub)
        self.testbed._register_stub('file',file_stub)

    def setUp(self):
        #FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
        #logging.basicConfig(format=FORMAT)
        #logging.getLogger('dash').setLevel(logging.INFO)

        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_blobstore_stub()
        self.testbed.init_files_stub()
        #self._init_blobstore_stub()
        self.testbed.init_taskqueue_stub()
        self.testbed.init_channel_stub()
        self.testbed.init_memcache_stub()
        # Clear ndb's in-context cache between tests.
        # This prevents data from leaking between tests.
        ndb.get_context().clear_cache()
                                        
        #self.testbed.setup_env(USER_EMAIL='usermail@gmail.com',USER_ID='1', USER_IS_ADMIN='0')
        self.testbed.init_user_stub()
        self.wsgi = webapp2.WSGIApplication(routes.webapp_routes, debug=True)
        #app.router.add(Route(r'/discover/<service_type:[\w\-_\.]+>/', handler='views.SearchHandler', parent="search", title="Search by type"))
        self.app = webtest.TestApp(self.wsgi, cookiejar=cookielib.CookieJar(), extra_environ={
            'REMOTE_USER':'test@example.com',
            'REMOTE_ADDR':'10.10.0.1', 
            'HTTP_X_APPENGINE_COUNTRY':'zz',
            'HTTP_USER_AGENT':'Mozilla/5.0 (GAE Unit test) Gecko/20100101 WebTest/2.0',
        })
        self.wsgi.router.add(webapp2.Route(template=r'/_ah/upload/<blob_id:[\w\-_\.]+>', handler=views.MediaHandler, name="uploadBlob_ah"))
        routes.routes['uploadBlob_ah'] = routes.routes['uploadBlob']
        self.auth = None
        self.uid="4d9cf5f4-4574-4381-9df3-1d6e7ca295ff"
        self.templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(__file__),'templates')
            ),
            extensions=['jinja2.ext.autoescape'],
            trim_blocks=False,
        )
        self.templates.filters['base64'] = utils.toBase64
        self.cgi_options = []
        drmloc = []
        for opt in options.options:
            if opt['name']=='drmloc':
                for loc in opt['options']:
                    if loc[1]:
                        drmloc.append(loc[1].split('=')[1])
        for opt in options.options:
            # the MSE option is exluded from the list as it does not change
            # anything in the manifest responses
            if opt['name'] in ['mse', 'drmloc']:
                continue
            opts = map(lambda o: o[1], opt['options'])
            if opt['name'] == 'drm':
                for d in opt['options']:
                    if d[1]=='drm=none':
                        continue
                    for loc in drmloc:
                        if "pro" in loc and d[1]!='drm=playready' and d[1]!='drm=all':
                            continue
                        opts.append(d[1]+'-'+loc)
            self.cgi_options.append((opt["name"],opts))
        #print(self.cgi_options)

    def setup_media(self):
        bbb = models.Stream(
            title='Big Buck Bunny', prefix='bbb',
            marlin_la_url='ms3://localhost/marlin/bbb',
            playready_la_url=drm.PlayReady.TEST_LA_URL
        )
        bbb.put()
        for idx, rid in enumerate(["bbb_v6","bbb_v6_enc","bbb_v7","bbb_v7_enc",
                                   "bbb_a1", "bbb_a1_enc", "bbb_a2"]):
            filename = rid + ".mp4"
            src_filename = os.path.join(os.path.dirname(__file__), "fixtures", filename)
            src = io.open(src_filename, mode="rb", buffering=16384)
            atoms = mp4.Mp4Atom.create(src)
            src.seek(0)
            data = src.read()
            src.close()
            blob_filename = files.blobstore.create(mime_type='video/mp4')
            with files.open(blob_filename, 'ab') as dest:
                dest.write(data)
            files.finalize(blob_filename)
            blob_key = files.blobstore.get_blob_key(blob_filename)
            rep = Representation.create(filename, atoms)
            self.assertAlmostEqual(rep.mediaDuration,
                                   self.MEDIA_DURATION*rep.timescale,
                                   delta=(rep.timescale / 10),
                                   msg='Invalid duration for {}. Expected {} got {}'.format(
                                       filename, self.MEDIA_DURATION*rep.timescale,
                                       rep.mediaDuration))
            mf = models.MediaFile(name=filename, rep=rep.toJSON(), blob=blob_key)
            mf.put()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for mf in media_files:
            r = mf.representation
            if r is None:
                continue
            if r.encrypted:
                mspr = drm.PlayReady(self.templates)
                for kid in r.kids:
                    key = binascii.b2a_hex(mspr.generate_content_key(kid.decode('hex')))
                    keypair = models.Key(hkid=kid, hkey=key, computed=True)
                    keypair.put()
        
    def tearDown(self):
        self.logoutCurrentUser()
        self.testbed.deactivate()
        if hasattr(TestCaseMixin, "_orig_assert_true"):
            TestCaseMixin._assert_true = TestCaseMixin._orig_assert_true
            del TestCaseMixin._orig_assert_true
        
    def from_uri(self, name, **kwargs):
        try:
            absolute = kwargs["absolute"]
            del kwargs["absolute"]
        except KeyError:
            absolute = False
        uri = routes.routes[name].formatTemplate.format(**kwargs)
        if absolute and not uri.startswith("http"):
            uri = 'http://testbed.example.com' + uri
        return uri
            
    def setCurrentUser(self, email=None, user_id=None, is_admin=False):
        if email is None:
            email = 'test@example.com'
        if user_id is None:
            user_id = 'test'
        is_admin = '1' if is_admin else '0'
        self.testbed.setup_env(
            user_email = email,
            user_id = user_id,
            user_is_admin = is_admin,
            overwrite = True
        )
        os.environ['USER_EMAIL'] = email
        os.environ['USER_ID'] = user_id
        os.environ['USER_IS_ADMIN'] = is_admin
        self.user = users.get_current_user()

    def logoutCurrentUser(self):
        self.setCurrentUser('', '', False)
        
    def upload_blobstore_file(self, from_url, upload_url, form, field, filename, contents, content_type = "application/octet-stream"):
        session = datastore.Get(upload_url.split('/')[-1])
        #new_object = "/" + session["gs_bucket_name"] + "/" + str(uuid.uuid4())
        new_object = "/gs{:s}".format(uuid.uuid4())
        #self.storage_stub.store(new_object, type, contents)

        message = [
            "Content-Length: " + str(len(contents)),
            'Content-Disposition: form-data; name="{}"; filename="{}"'.format(field, filename),
            'Content-Type: {}'.format(content_type),
            "Content-MD5: " + base64.b64encode(md5.new(contents).hexdigest()),
            "X-AppEngine-Cloud-Storage-Object: /gs" + new_object.encode("ascii"),
            'X-AppEngine-Upload-Creation: 2019-07-17 16:19:55.531719',
            ''
        ]
        message = '\r\n'.join(message)
        cookies=[]
        for k,v in self.app.cookies.iteritems():
            cookies.append('{}={}'.format(k,v))
        headers = {
            "Cookie": '; '.join(cookies),
            "Referer": from_url,
        }
        upload_files = [(field, filename, message, "message/external-body; blob-key=\"encoded_gs_file:blablabla\"; access-type=\"X-AppEngine-BlobKey\"")]
        #upload_files = [(field, filename, message, 'fooooo')]
        logging.debug(message)
        return self.app.post(upload_url, params=form, headers=headers, upload_files=upload_files)

    def progress(self, pos, total):
        if pos == 0:
            sys.stdout.write('\n')
        sys.stdout.write('\r {:05.2f}%'.format(100.0 * float(pos) / float(total)))
        if pos == total:
            sys.stdout.write('\n')
        sys.stdout.flush()

class ViewsTestDashValidator(dash.DashValidator):
    def __init__(self, app, mode, mpd, url):
        opts = dash.Options(strict=True)
        opts.log = logging.getLogger(__name__)
        opts.log.addFilter(HideMixinsFilter())
        #opts.log.setLevel(logging.DEBUG)
        super(ViewsTestDashValidator, self).__init__(url, app, mode=mode, options=opts)
        self.representations = {}
        self.log.debug('Check manifest: %s', url)
        
    def get_representation_info(self, representation):
        try:
            return self.representations[representation.unique_id()]
        except KeyError:
            pass
        url = representation.init_seg_url()
        parts = urlparse.urlparse(url)
        #self.log.debug('match %s %s', routes.routes["dash-media"].reTemplate.pattern, parts.path)
        match = routes.routes["dash-media"].reTemplate.match(parts.path)
        if match is None:
            #self.log.debug('match %s', routes.routes["dash-od-media"].reTemplate.pattern)
            match = routes.routes["dash-od-media"].reTemplate.match(parts.path)
        if match is None:
            self.log.error('match %s %s', url, parts.path)
        self.assertIsNotNone(match)
        #filename = os.path.basename(parts.path)
        filename = match.group("filename")
        #name, ext = os.path.splitext(filename)
        name = filename + '.mp4'
        #self.log.debug("get_representation_info %s %s %s", url, filename, name)
        mf = models.MediaFile.query(models.MediaFile.name==name).get()
        if mf is None:
            filename = os.path.dirname(parts.path).split('/')[-1]
            name = filename + '.mp4'
            mf = models.MediaFile.query(models.MediaFile.name==name).get()
        self.assertIsNotNone(mf)
        rep = mf.representation
        info = dash.RepresentationInfo(num_segments=rep.num_segments, **rep.toJSON())
        self.set_representation_info(representation, info)
        return info

    def set_representation_info(self, representation, info):
        self.representations[representation.unique_id()] = info
        
class TestHandlers(GAETestCase):
    def test_index_page(self):
        self.setup_media()
        page = views.MainPage()
        self.assertIsNotNone(getattr(page,'get',None))
        url = self.from_uri('home', absolute=True)
        self.logoutCurrentUser()
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        response.mustcontain('Log In', no='href="{}"'.format(self.from_uri('media-index')))
        for filename, manifest in manifests.manifest.iteritems():
            mpd_url = self.from_uri('dash-mpd-v3', manifest=filename, stream='placeholder',
                                    mode='live')
            mpd_url = mpd_url.replace('/placeholder/', '/{directory}/')
            mpd_url = mpd_url.replace('/live/', '/{mode}/')
            response.mustcontain(mpd_url)
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        response.mustcontain('href="{}"'.format(self.from_uri('media-index')), no="Log In")
        response.mustcontain('Log Out')

        #self.setCurrentUser(is_admin=False)
        #response = self.app.get(url)
        #response.mustcontain('<a href="',mpd_url, no=routes.routes['upload'].title)
        
    def test_media_page(self):
        self.setup_media()
        page = views.MediaHandler()
        self.assertIsNotNone(getattr(page,'get',None))
        self.assertIsNotNone(getattr(page,'post',None))
        url = self.from_uri('media-index', absolute=True)

        # user must be logged in to use media page
        self.logoutCurrentUser()
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int,401)
        
        # user must be logged in as admin to use media page
        self.setCurrentUser(is_admin=False)
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int,401)
        
        # user must be logged in as admin to use media page
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        
    def check_manifest(self, filename, indexes, tested):
        #def _assert_true(self, result, a, b, msg, template):
        #    if not result:
        #        if msg is not None:
        #            raise AssertionError(msg)
        #        raise AssertionError(template.format(a,b))

        params = {}
        mode = None
        for idx, option in enumerate(self.cgi_options):
            name, values = option
            value = values[indexes[idx]]
            if name=='mode':
                mode = value[5:]
            elif value:
                params[name] = value
        # remove pointless combinations of options
        if mode not in manifests.manifest[filename]['modes']:
            return
        if mode != "live":
            if params.has_key("mup"):
                del params["mup"]
            if params.has_key("time"):
                del params["time"]
        cgi = params.values()
        url = self.from_uri('dash-mpd-v3', manifest=filename, mode=mode, stream='bbb')
        mpd_url = '{}?{}'.format(url, '&'.join(cgi))
        if mpd_url in tested:
            return
        tested.add(mpd_url)
        #print('mpd_url', mpd_url)
        response = self.app.get(mpd_url)
        dv = ViewsTestDashValidator(self.app, mode, response.xml, mpd_url)
        dv.validate(depth=2)
        if mode != 'live':
            if dv.manifest.mediaPresentationDuration is None:
                # duration must be specified in the Period
                dur = datetime.timedelta(seconds=0)
                for period in dv.manifest.periods:
                    self.assertIsNotNone(period.duration)
                    dur += period.duration
                self.assertAlmostEqual(dur.total_seconds(), self.MEDIA_DURATION,
                                       delta=1.0)
            else:
                self.assertAlmostEqual(dv.manifest.mediaPresentationDuration.total_seconds(),
                                       self.MEDIA_DURATION, delta=1.0)

    def check_a_manifest_using_all_options(self, filename, manifest):
        """Exhaustive test of a manifest with every combination of options.
        This test is _very_ slow, expect it to take several minutes!"""
        self.setup_media()
        self.logoutCurrentUser()
        pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        # do a first pass check with no CGI options
        for mode in ['vod', 'live', 'odvod']:
            if mode not in manifest['modes']:
                continue
            url = self.from_uri('dash-mpd-v3', manifest=filename, mode=mode, stream='bbb')
            response = self.app.get(url)
            TestCaseMixin._orig_assert_true = TestCaseMixin._assert_true
            TestCaseMixin._assert_true = add_url(TestCaseMixin._assert_true, url)
            mpd = ViewsTestDashValidator(self.app, mode, response.xml, url)
            mpd.validate(depth=2)
            TestCaseMixin._assert_true = TestCaseMixin._orig_assert_true
            del TestCaseMixin._orig_assert_true

        # do the exhaustive check of every option
        total_tests = 1
        count = 0
        for param in self.cgi_options:
            total_tests = total_tests * len(param[1])
        tested = set([url])
        indexes = [0] * len(self.cgi_options)
        done = False
        while not done:
            self.progress(count, total_tests)
            count += 1
            self.check_manifest(filename, indexes, tested)
            idx = 0
            while idx < len(self.cgi_options):
                indexes[idx] += 1
                if indexes[idx] < len(self.cgi_options[idx][1]):
                    break
                indexes[idx] = 0
                idx += 1
            if idx==len(self.cgi_options):
                done=True
        self.progress(total_tests, total_tests)

    def test_availability_start_time(self):
        """Control of MPD@availabilityStartTime using the start parameter"""
        self.setup_media()
        self.logoutCurrentUser()
        drm_options = None
        for o in self.cgi_options:
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        ref_now = real_datetime_class(2019,1,1,4,5,6, tzinfo=utils.UTC())
        ref_today = real_datetime_class(2019,1,1, tzinfo=utils.UTC())
        ref_yesterday = ref_today - datetime.timedelta(days=1)
        testcases = [
            ('', ref_now, ref_today),
            ('today', ref_now, ref_today),
            ('2019-09-invalid-iso-datetime', ref_now, ref_today),
            ('now', ref_now, ref_now),
            ('epoch', ref_now, datetime.datetime(1970, 1, 1, 0, 0, tzinfo=utils.UTC())),
            ('2009-02-27T10:00:00Z', ref_now, datetime.datetime(2009,2,27,10,0,0, tzinfo=utils.UTC()) ),
            ('2013-07-25T09:57:31Z', ref_now, datetime.datetime(2013,7,25,9,57,31, tzinfo=utils.UTC()) ),
            # special case when "now" is midnight, use yesterday midnight as availabilityStartTime
            ('', ref_today, ref_yesterday),
        ]
        msg=r'When start="%s" is used, expected MPD@availabilityStartTime to be %s but was %s'
        for option, now, start_time in testcases:
            with mock_datetime_now(now):
                baseurl = self.from_uri('dash-mpd-v3', manifest=filename, stream='bbb', mode='live')
                if option:
                    baseurl += '?start=' + option
                response = self.app.get(baseurl)
                dv = ViewsTestDashValidator(self.app, 'live', response.xml, baseurl)
                dv.validate(depth=3)
                if option=='now':
                    start_time = dv.manifest.publishTime - dv.manifest.timeShiftBufferDepth
                self.assertEqual(dv.manifest.availabilityStartTime, start_time,
                                 msg=msg%(option, start_time.isoformat(),
                                          dv.manifest.availabilityStartTime.isoformat()))

    def test_get_vod_media_using_live_profile(self):
        """Get VoD segments for each DRM type (live profile)"""
        self.setup_media()
        self.logoutCurrentUser()
        drm_options = None
        for o in self.cgi_options:
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        # pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        total_tests = len(drm_options)
        test_count = 0
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        for drm_opt in drm_options:
            self.progress(test_count, total_tests)
            test_count += 1
            baseurl = self.from_uri('dash-mpd-v2', manifest=filename, stream='bbb')
            baseurl += '?mode=vod&' + drm_opt
            response = self.app.get(baseurl)
            mpd = ViewsTestDashValidator(self.app, 'vod', response.xml, baseurl)
            mpd.validate()
        self.progress(total_tests, total_tests)

    def test_get_live_media_using_live_profile(self):
        """Get segments from a live stream for each DRM type (live profile)"""
        self.setup_media()
        self.logoutCurrentUser()
        drm_options = None
        for o in self.cgi_options:
            if o[0] == 'drm':
                drm_options = o[1]
                break
        self.assertIsNotNone(drm_options)
        pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        total_tests = len(drm_options)
        test_count = 0
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        for drm_opt in drm_options:
            self.progress(test_count, total_tests)
            test_count += 1
            now = datetime.datetime.now(tz=utils.UTC())
            availabilityStartTime = now - datetime.timedelta(minutes=test_count)
            availabilityStartTime = utils.toIsoDateTime(availabilityStartTime)
            baseurl = self.from_uri('dash-mpd-v2', manifest=filename, stream='bbb')
            baseurl += '?mode=live&' + drm_opt + '&start='+availabilityStartTime
            response = self.app.get(baseurl)
            self.assertEqual(response.status_int, 200)
            mpd = ViewsTestDashValidator(self.app, "live", response.xml, baseurl)
            mpd.validate()
        self.progress(total_tests, total_tests)

    def test_get_vod_media_using_on_demand_profile(self):
        """Get VoD segments (on-demand profile)"""
        self.logoutCurrentUser()
        self.setup_media()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for filename, manifest in manifests.manifest.iteritems():
            if 'odvod' not in manifest['modes']:
                continue
            baseurl = self.from_uri('dash-mpd-v3', mode='odvod', manifest=filename, stream='bbb')
            response = self.app.get(baseurl)
            self.assertIn("urn:mpeg:dash:profile:isoff-on-demand:2011", response.xml.get('profiles'))
            mpd = ViewsTestDashValidator(self.app, "odvod", response.xml, baseurl)
            mpd.validate()

    def test_request_unknown_media(self):
        url = self.from_uri("dash-media", mode="vod", filename="notfound", segment_num=1, ext="mp4")
        response = self.app.get(url, status=404)
        
    def test_playready_la_url(self):
        """
        PlayReady LA_URL in the manifest
        """
        # TODO: don't hard code KID
        test_la_url = drm.PlayReady.TEST_LA_URL.format(
            cfgs='(kid:QFS0GixTmUOU3Fxa2VhLrA==,persist:false,sl:150)')
        self.check_playready_la_url_value(test_la_url, [])
        
    def test_playready_la_url_override(self):
        """
        Replace LA_URL in stream with CGI playready_la_url parameter
        """
        test_la_url = 'https://licence.url.override/'
        self.check_playready_la_url_value(
            test_la_url,
            ['playready_la_url={0}'.format(urllib.quote_plus(test_la_url))])
        
    def check_playready_la_url_value(self, test_la_url, args):
        """
        Check the LA_URL in the PRO element is correct
        """
        self.setup_media()
        self.logoutCurrentUser()
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        baseurl = self.from_uri('dash-mpd-v2', manifest=filename, stream='bbb')
        args += ['mode=vod', 'drm=playready']
        baseurl += '?' + '&'.join(args)
        response = self.app.get(baseurl)
        mpd = ViewsTestDashValidator(self.app, 'vod', response.xml, baseurl)
        mpd.validate()
        self.assertEqual(len(mpd.manifest.periods), 1)
        schemeIdUri = "urn:uuid:" + drm.PlayReady.SYSTEM_ID.upper()
        pro_tag = "{{{0}}}pro".format(mpd.xmlNamespaces['mspr'])
        for adap_set in mpd.manifest.periods[0].adaptation_sets:
            for prot in adap_set.contentProtection:
                if prot.schemeIdUri != schemeIdUri:
                    continue
                for elt in prot.children:
                    if elt.tag != pro_tag:
                        continue
                    pro = base64.b64decode(elt.text)
                    for record in drm.PlayReady.parse_pro(utils.BufferedReader(None, data=pro)):
                        la_urls = record['xml'].findall(
                            './prh:DATA/prh:LA_URL', mpd.xmlNamespaces)
                        self.assertEqual(len(la_urls), 1)
                        self.assertEqual(la_urls[0].text, test_la_url)
        
    def test_injected_http_error_codes(self):
        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for seg in range(1,5):
            url = self.from_uri("dash-media", mode="vod",
                                filename=media_files[0].representation.id,
                                segment_num=seg, ext="mp4", absolute=True)
            response = self.app.get(url)
            for code in [404, 410, 503, 504]:
                if seg in [1,3]:
                    status=code
                else:
                    status=200
                response = self.app.get(url, {str(code): '1,3'}, status=status)

    def test_video_corruption(self):
        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        for seg in range(1,5):
            url = self.from_uri("dash-media", mode="vod",
                                filename=media_files[0].representation.id,
                                segment_num=seg, ext="mp4", absolute=True)
            clean = self.app.get(url)
            corrupt = self.app.get(url, {'corrupt': '1,2'})
            if seg < 3:
                self.assertNotEqual(clean.body, corrupt.body)
            else:
                self.assertEqual(clean.body, corrupt.body)

    @staticmethod
    def cgi_combinations(cgi_options):
        """convert a list of CGI options into a set of all possible combinations"""
        indexes = [0] * len(cgi_options)
        result = set()
        done = False
        while not done:
            params = {}
            mode = None
            for idx, option in enumerate(cgi_options):
                name, values = option
                value = values[indexes[idx]]
                if name=='mode':
                    mode = value[5:]
                if value:
                    params[name] = value
            if mode in manifests.manifest[filename]['modes']:
                if mode != "live":
                    if params.has_key("mup"):
                        del params["mup"]
                    if params.has_key("time"):
                        del params["time"]
                cgi = '&'.join(params.values())
                result.add(cgi)
            idx = 0
            while idx < len(cgi_options):
                indexes[idx] += 1
                if indexes[idx] < len(cgi_options[idx][1]):
                    break
                indexes[idx] = 0
                idx += 1
            if idx == len(cgi_options):
                done = True
        return result
        
    def test_video_playback(self):
        """Test generating the video HTML page.
        Checks every manifest with every CGI parameter causes a valid
        HTML page that allows the video to be watched using a <video> element.
        """
        def opt_choose(item):
            return item[0] in ['mode', 'acodec', 'drm']

        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreaterThan(len(media_files), 0)
        url = self.from_uri("video", absolute=True)
        options = filter(opt_choose, self.cgi_options)
        options = self.cgi_combinations(options)
        num_tests = (len(options) * len(models.Stream.all()) *
                     len(manifests.manifest))
        count = 0
        for filename, manifest in manifests.manifest.iteritems():
            for stream in models.Stream.all():
                for opt in options:
                    html_url = url+'?mpd={prefix}/{mpd}&{opt}'.format(
                        prefix=stream.prefix, mpd=filename, opt=opt)
                    self.progress(count, num_tests)
                    response = self.app.get(html_url)
                    html = response.html
                    self.assertEqual(html.title.string, manifest['title'])
                    for script in html.find_all('script'):
                        if script.get("src"):
                            continue
                        script = script.get_text()
                        self.assertIn('var dashParameters', script)
                        start = script.index('{')
                        end = script.rindex('}') + 1
                        script = json.loads(script[start:end])
                        for field in ['title', 'prefix', 'playready_la_url', 'marlin_la_url']:
                            self.assertEqual(script['stream'][field], getattr(stream, field))
                    count += 1
        self.progress(num_tests, num_tests)

    def test_add_stream(self):
        self.assertEqual(len(models.Stream.all()), 0)
        request = {
            'title': 'Big Buck Bunny',
            'prefix': 'bbb',
            'marlin_la_url': 'ms3://unit.test/bbb.sas',
            'playready_la_url':''
        }
        params = []
        for k, v in request.iteritems():
            params.append('{0}={1}'.format(k, urllib.quote(v)))
        url = self.from_uri('stream', absolute=True)
        url = '{0}?{1}'.format(url, '&'.join(params))

        # user must be logged in to use stream API
        self.logoutCurrentUser()
        response = self.app.put(url, status=401)

        # user must be logged in as admin to use stream API
        self.setCurrentUser(is_admin=False)
        response = self.app.put(url, status=401)

        # user must be logged in as admin to use stream API
        self.setCurrentUser(is_admin=True)

        # request should fail due to lack of CSRF token
        response = self.app.put(url)
        self.assertTrue(response.json.has_key("error"))
        self.assertIn("CsrfFailureException", response.json["error"])

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        streams_table = media.html.find(id="streams")
        request['csrf_token'] = streams_table.get('data-csrf')
        url += '&csrf_token=' + request['csrf_token']
        response = self.app.put(url)
        expected_result = copy.deepcopy(request)
        expected_result['playready_la_url'] = None
        del expected_result['csrf_token']
        expected_result['csrf'] = response.json["csrf"]
        expected_result['id'] = response.json["id"]
        self.assertEqual(expected_result, response.json)

        streams = models.Stream.all()
        self.assertEqual(len(streams), 1)
        for k, v in request.iteritems():
            if k == 'csrf_token':
                continue
            self.assertEqual(getattr(streams[0], k), expected_result[k],
                             'Field {0}: expected "{1}" got "{2}"'.format(k, getattr(streams[0], k),
                                                                          expected_result[k]))

        url = self.from_uri('media-index', absolute=True)
        response = self.app.get(url)
        response.mustcontain(expected_result['title'], expected_result['prefix'])

    def test_delete_stream(self):
        self.assertEqual(len(models.Stream.all()), 0)

        bbb = models.Stream(title='Big Buck Bunny', prefix='bbb')
        bbb.put()
        tears = models.Stream(title='Tears of Steel', prefix='tears')
        tears.put()
        self.assertEqual(len(models.Stream.all()), 2)

        url = self.from_uri('del-stream', id=bbb.key.urlsafe(), absolute=True)

        # user must be logged in to use stream API
        self.logoutCurrentUser()
        response = self.app.delete(url, status=401)
        self.assertEqual(len(models.Stream.all()), 2)

        # user must be logged in as admin to use stream API
        self.setCurrentUser(is_admin=False)
        response = self.app.delete(url, status=401)
        self.assertEqual(response.status_int,401)
        self.assertEqual(len(models.Stream.all()), 2)

        # user must be logged in as admin to use stream API
        self.setCurrentUser(is_admin=True)

        # request without CSRF token should fail
        response = self.app.delete(url)
        self.assertTrue(response.json.has_key("error"))
        self.assertIn("CsrfFailureException", response.json["error"])
        self.assertEqual(len(models.Stream.all()), 2)

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        streams_table = media.html.find(id="streams")
        csrf_url = url + '?csrf_token=' + streams_table.get('data-csrf')

        response = self.app.delete(csrf_url)
        streams = models.Stream.all()
        self.assertEqual(len(streams), 1)
        next_csrf_token = response.json["csrf"]

        # try to re-use a CSRF token
        reuse_url = self.from_uri('del-stream', id=tears.key.urlsafe(), absolute=True)
        reuse_url += '?csrf_token=' + streams_table.get('data-csrf')
        response = self.app.delete(reuse_url)
        self.assertTrue(response.json.has_key("error"))
        self.assertIn("CsrfFailureException", response.json["error"])

        # try to delete a stream that does not exist
        response = self.app.delete(url+'?csrf_token='+next_csrf_token, status=404)

    def test_add_full_key_pair(self):
        self.assertEqual(len(models.Key.all()), 0)
        
        url = self.from_uri('key', absolute=True)

        request = {
            'kid': '1AB45440532C439994DC5C5AD9584BAC',
            'key': 'ccc0f2b3b279926496a7f5d25da692f6',
        }
        url = '{}?kid={}&key={}'.format(url, request['kid'], request['key'])

        # user must be logged in to use keys API
        self.logoutCurrentUser()
        response = self.app.put(url, status=401)
        self.assertEqual(response.status_int,401)
        
        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=False)
        response = self.app.put(url, status=401)
        self.assertEqual(response.status_int,401)
        
        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=True)

        # request should fail due to lack of CSRF token
        response = self.app.put(url)
        self.assertTrue(response.json.has_key("error"))
        self.assertIn("CsrfFailureException", response.json["error"])

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        keys_table = media.html.find(id="keys")
        url += '&csrf_token=' + keys_table.get('data-csrf')
        response = self.app.put(url)
        expected_result = {
            'kid': request['kid'].lower(),
            'key': request['key'].lower(),
            'computed': False,
            'csrf': response.json["csrf"],
        }
        self.assertEqual(expected_result, response.json)

        keys = models.Key.all()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, expected_result['kid'])
        self.assertEqual(keys[0].hkey, expected_result['key'])
        self.assertEqual(keys[0].computed, False)

        url = self.from_uri('media-index', absolute=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int, 200)
        response.mustcontain(expected_result['kid'], expected_result['key'])        

    def test_add_computed_keys(self):
        self.assertEqual(len(models.Key.all()), 0)
        kid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').lower()
        url = '{}?kid={}'.format(self.from_uri('key', absolute=True), kid)
        self.setCurrentUser(is_admin=True)
        response = self.app.put(url)
        # request without CSRF token should fail
        self.assertTrue(response.json.has_key("error"))
        self.assertIn("CsrfFailureException", response.json["error"])

        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        keys_table = media.html.find(id="keys")
        url += '&csrf_token=' + keys_table.get('data-csrf')
        response = self.app.put(url)
        expected_result = {
            'kid': kid,
            'key': base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
            'computed': True,
            'csrf': response.json["csrf"],
        }
        self.assertEqual(expected_result, response.json)
        keys = models.Key.all()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, expected_result['kid'])
        self.assertEqual(keys[0].hkey, expected_result['key'])
        self.assertEqual(keys[0].computed, True)
        
    def test_delete_key(self):
        self.assertEqual(len(models.Key.all()), 0)

        kid='1AB45440532C439994DC5C5AD9584BAC'.lower()
        keypair = models.Key(hkid=kid,
                             hkey='ccc0f2b3b279926496a7f5d25da692f6',
                             computed=False)
        keypair.put()
        
        keypair = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').lower(),
                             hkey=base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                             computed=True)
        keypair.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('del-key', kid=kid, absolute=True)
        
        # user must be logged in to use keys API
        self.logoutCurrentUser()
        response = self.app.delete(url, status=401)
        self.assertEqual(response.status_int,401)
        self.assertEqual(len(models.Key.all()), 2)
        
        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=False)
        response = self.app.delete(url, status=401)
        self.assertEqual(response.status_int,401)
        self.assertEqual(len(models.Key.all()), 2)

        # user must be logged in as admin to use keys API
        self.setCurrentUser(is_admin=True)

        # request without CSRF token should fail
        response = self.app.delete(url)
        self.assertTrue(response.json.has_key("error"))
        self.assertIn("CsrfFailureException", response.json["error"])
        
        media_url = self.from_uri('media-index', absolute=True)
        media = self.app.get(media_url)
        keys_table = media.html.find(id="keys")
        csrf_url = url + '?csrf_token=' + keys_table.get('data-csrf')

        response = self.app.delete(csrf_url)
        self.assertEqual(response.status_int, 200)
        keys = models.Key.all()
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0].hkid, keypair.hkid)
        self.assertEqual(keys[0].hkey, keypair.hkey)
        self.assertEqual(keys[0].computed, keypair.computed)
        next_csrf_token = response.json["csrf"]

        # try to re-use a CSRF token
        response = self.app.delete(csrf_url)
        self.assertTrue(response.json.has_key("error"))
        self.assertIn("CsrfFailureException", response.json["error"])

        # try to delete a key that does not exist
        response = self.app.delete(url+'?csrf_token='+next_csrf_token)
        self.assertTrue(response.json.has_key("error"))
        self.assertIn("not found", response.json["error"])
        next_csrf_token = response.json["csrf"]

        url = self.from_uri('del-key', kid='invalid', absolute=True)
        try:
            binascii.unhexlify('invalid')
        except (TypeError) as err:
            expected_result = {
                'error': '{}: {:s}'.format(err.__class__.__name__, err)
            }
        response = self.app.delete(url + '?csrf_token=' + next_csrf_token)
        expected_result["csrf"] = response.json["csrf"]
        self.assertEqual(expected_result, response.json)
        
    def test_clearkey(self):
        self.assertEqual(len(models.Key.all()), 0)

        keypair1 = models.Key(hkid='1AB45440532C439994DC5C5AD9584BAC'.lower(),
                             hkey='ccc0f2b3b279926496a7f5d25da692f6',
                             computed=False)
        keypair1.put()

        keypair2 = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').lower(),
                             hkey=base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                             computed=True)
        keypair2.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('clearkey', absolute=True)
        request = {
            "kids": [
                self.base64url_encode(keypair1.hkid),
                self.base64url_encode(keypair2.hkid),
            ],
            "type":"temporary",
        }
        
        # user does not need to be logged in to use clearkey
        self.logoutCurrentUser()
        response = self.app.post_json(url, request)
        expected_result = {
            "keys": [
                {
                    "kty": "oct",
                    "kid": self.base64url_encode(keypair1.hkid),
                    "k": self.base64url_encode(keypair1.hkey),
                },
                {
                    "kty": "oct",
                    "kid": self.base64url_encode(keypair2.hkid),
                    "k": self.base64url_encode(keypair2.hkey),
                },
            ],
            "type":"temporary",
        }
        # as the order of keys is not defined, sort both expected
        # and actual before the compare
        expected_result["keys"].sort(key=lambda k: k["kid"])
        actual_result = copy.deepcopy(response.json)
        actual_result["keys"].sort(key=lambda k: k["kid"])
        self.maxDiff = None
        self.assertEqual(expected_result, actual_result)

        # check with unknown KID
        request = {
            "kids": [
                self.base64url_encode(keypair1.hkid.replace('0','9')),
            ],
            "type":"temporary",
        }
        expected_result = {
            "keys": [],
            "type":"temporary",
        }
        response = self.app.post_json(url, request)
        self.assertEqual(expected_result, response.json)

    def test_clearkey_bad_request(self):
        self.assertEqual(len(models.Key.all()), 0)

        keypair1 = models.Key(hkid='1AB45440532C439994DC5C5AD9584BAC'.lower(),
                             hkey='ccc0f2b3b279926496a7f5d25da692f6',
                             computed=False)
        keypair1.put()

        keypair2 = models.Key(hkid='01020304-0506-0708-090A-AABBCCDDEEFF'.replace('-','').lower(),
                             hkey=base64.b64decode('GUf166PQbx+sgBADjyBMvw==').encode('hex'),
                             computed=True)
        keypair2.put()
        self.assertEqual(len(models.Key.all()), 2)

        url = self.from_uri('clearkey', absolute=True)

        # user does not need to be logged in to use clearkey
        self.logoutCurrentUser()

        request = {
            "type":"temporary",
        }

        # check request without the kids parameter
        response = self.app.post_json(url, request)
        expected_result = {
            'error': "KeyError: 'kids'",
        }
        self.assertEqual(expected_result, response.json)

        # check request with invalid base64url encoding
        request = {
            "kids": [
                '*invalid base64*',
            ],
            "type":"temporary",
        }
        
        response = self.app.post_json(url, request)
        try:
            base64.b64decode('*invalid base64*')
        except (TypeError) as err:
            expected_result = {
                "error": '{}: {:s}'.format(err.__class__.__name__, err)
            }
        self.assertEqual(expected_result, response.json)

    def base64url_encode(self, value):
        #See https://tools.ietf.org/html/rfc7515#page-54
        if len(value) != 16:
            value = value.decode('hex')
        s = base64.b64encode(value) # Regular base64 encoder
        s = s.split('=')[0]         # Remove any trailing '='s
        s = s.replace('+', '-')     # 62nd char of encoding
        s = s.replace('/', '_')     # 63rd char of encoding
        return s
        
    def test_upload_media_file(self):
        self.upload_media_file(0)

    def test_upload_media_file_using_ajax(self):
        self.upload_media_file(1)

    def upload_media_file(self, ajax):
        url = self.from_uri('media-index', absolute=True)
        blobURL = self.from_uri('uploadBlob', absolute=True)
        self.assertIsNotNone(blobURL)
        
        # not logged in, should return authentication error
        self.logoutCurrentUser()
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int,401)

        # logged in as non-admin, should return authentication error
        self.setCurrentUser(is_admin=False)
        response = self.app.get(url, status=401)
        self.assertEqual(response.status_int,401)

        # logged in as admin should succeed
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)

        form = response.forms['upload-form']
        form['file'] = webtest.Upload('bbb_v1.mp4', b'data', 'video/mp4')
        #form['media'] = 'V1'
        self.assertEqual(form.method, 'POST')
        self.logoutCurrentUser()
        # a POST from a non-logged in user should fail
        response = form.submit('submit', status=401)
        
        self.setCurrentUser(is_admin=True)
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        upload_form = response.forms['upload-form']
        form = {
            "csrf_token": upload_form["csrf_token"].value,
            "ajax": ajax,
            "submit": "submit",
        }
        response = self.upload_blobstore_file(url, response.forms['upload-form'].action,
                                              form, 'file', 'bbb_v1.mp4', b'data',
                                              'video/mp4')
        if ajax:
            expected_result = {
                'csrf':0,
                'name': 'bbb_v1.mp4',
            }
            for item in ['csrf', 'upload_url', 'file_html', 'key', 'blob',
                         'representation']:
                self.assertTrue(response.json.has_key(item))
                expected_result[item] = response.json[item]
            self.assertNotEqual(response.json['csrf'], form['csrf_token'])
            self.assertEqual(response.json, expected_result)
        else:
            response.mustcontain('<h2>Upload complete</h2>')
        
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        response.mustcontain('bbb_v1.mp4')

def gen_test_fn(filename, manifest):
    def run_test(self):
        self.check_a_manifest_using_all_options(filename, manifest)
    return run_test

for filename, manifest in manifests.manifest.iteritems():
    name = filename[:-4] # remove '.mpd'
    if 'manifest' not in name:
        name = name + '_manifest'
    setattr(TestHandlers, "test_all_options_%s"%(name), gen_test_fn(filename, manifest))
    
if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestHandlers)

if __name__ == '__main__':
    unittest.main()        
