
import base64
import binascii
import cookielib
import copy
import datetime
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
import urlparse
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

import drm
import models
import mp4
import views
import utils
import manifests
import options
import routes
from segment import Representation

# convert App Engine's template syntax in to the Python string format syntax
for name,r in routes.routes.iteritems():
    r.template = re.sub(r':[^>]*>','}',r.template.replace('<','{'))

class TestCaseMixin(object):
    def _assert_true(self, result, a, b, msg, template):
        if not result:
            if msg is not None:
                raise AssertionError(msg)
            raise AssertionError(template.format(a,b))

    def assertTrue(self, result, msg=None):
        self._assert_true(result, result, None, msg, r'{} not True')

    def assertFalse(self, result, msg=None):
        self._assert_true(not result, result, None, msg, r'{} not False')

    def assertEqual(self, a, b, msg=None):
        self._assert_true(a==b, a, b, msg, r'{} != {}')

    def assertGreaterThan(self, a, b, msg=None):
        self._assert_true(a>b, a, b, msg, r'{} <= {}')

    def assertGreaterThanOrEqual(self, a, b, msg=None):
        self._assert_true(a>=b, a, b, msg, r'{} < {}')

    def assertLessThan(self, a, b, msg=None):
        self._assert_true(a<b, a, b, msg, r'{} >= {}')

    def assertLessThanOrEqual(self, a, b, msg=None):
        self._assert_true(a<=b, a, b, msg, r'{} > {}')

    def assertIn(self, a, b, msg=None):
        self._assert_true(a in b, a, b, msg, r'{} not in {}')

    def assertNotIn(self, a, b, msg=None):
        self._assert_true(a not in b, a, b, msg, r'{} in {}')

    def assertIsNone(self, a, msg=None):
        self._assert_true(a is None, a, None, msg, r'{} is not None')

    def assertIsNotNone(self, a, msg=None):
        self._assert_true(a is not None, a, None, msg, r'{} is None')

    def assertEndsWith(self, a, b, msg=None):
        self._assert_true(a.endswith(b), a, b, msg, r'{} does not end with {}')

    def assertIsInstance(self, a, types, msg=None):
        self._assert_true(isinstance(a, types), a, types, msg, r'{} is not instance of {}')


class GAETestCase(TestCaseMixin, unittest.TestCase):
    def _init_blobstore_stub(self):
        blob_storage = file_blob_storage.FileBlobStorage('tmp', testbed.DEFAULT_APP_ID)
        blob_stub = blobstore_stub.BlobstoreServiceStub(blob_storage)
        file_stub = file_service_stub.FileServiceStub(blob_storage)
        self.testbed._register_stub('blobstore',blob_stub)
        self.testbed._register_stub('file',file_stub)

    def setUp(self):
        FORMAT = "%(filename)s:%(lineno)d %(message)s"
        #logging.basicConfig(format=FORMAT)
        #logging.getLogger().setLevel(logging.DEBUG)

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
        for idx, rid in enumerate(["bbb_v6","bbb_v6_enc","bbb_v7","bbb_v7_enc",
                                   "bbb_a1", "bbb_a1_enc"]):
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
            mf = models.MediaFile(name=filename, rep=rep.toJSON(), blob=blob_key)
            mf.put()
        media_files = models.MediaFile.all()
        self.assertGreater(len(media_files), 0)
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
        
    def from_uri(self, name, **kwargs):
        try:
            absolute = kwargs["absolute"]
            del kwargs["absolute"]
        except KeyError:
            absolute = False
        uri = routes.routes[name].template.format(**kwargs)
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


class DashElement(TestCaseMixin):
    xmlNamespaces = {
        'dash': 'urn:mpeg:dash:schema:mpd:2011',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'cenc': 'urn:mpeg:cenc:2013',
    }

    def __init__(self, elt, parent):
        self.element = elt
        self.parent = parent
        if parent:
            self.mode = parent.mode
        base = elt.findall('./dash:BaseURL', self.xmlNamespaces)
        if base:
            self.baseurl = base[0].text
        elif parent:
            self.baseurl = parent.baseurl
        else:
            self.baseurl = None
        self.id = elt.get('id')

    @property
    def mpd(self):
        if self.parent:
            return self.parent.mpd
        return self


class DashManifest(DashElement):
    def __init__(self, mode, mpd, url):
        super(DashManifest, self).__init__(mpd, None)
        self.url = url
        self.mode = mode
        if self.baseurl is None:
            self.baseurl = url
            assert isinstance(url, basestring)
        if mode=='live':
            self.availabilityStartTime = utils.from_isodatetime(mpd.get("availabilityStartTime"))
            self.timeShiftBufferDepth = utils.from_isodatetime(mpd.get("timeShiftBufferDepth"))
        else:
            self.mediaPresentationDuration = utils.from_isodatetime(mpd.get("mediaPresentationDuration"))
            if "urn:mpeg:dash:profile:isoff-on-demand:2011" in mpd.get('profiles'):
                self.mode = 'odvod'
        self.publishTime = mpd.get("publishTime")
        if self.publishTime is not None:
            self.publishTime = utils.from_isodatetime(self.publishTime)
        self.periods = map(lambda p: DashPeriod(p, self),
                           self.element.findall('./dash:Period', self.xmlNamespaces))

    def validate(self):
        root = self.element
        mpd_type = root.get("type", "static")
        period = root.find('dash:Period', self.xmlNamespaces)
        self.assertIsNotNone(period, "Manifest does not have a Period element: %s"%self.url)
        if self.mode=="live":
            self.assertEqual(mpd_type, "dynamic",
                             "MPD@type must be dynamic for live manifest: %s"%self.url)
            self.assertIsNotNone(root.get("availabilityStartTime"),
                                 "MPD@availabilityStartTime must be present for live manifest: %s"%self.url)
            self.assertIsNone(root.get("mediaPresentationDuration"),
                              "MPD@mediaPresentationDuration must not be present for live manifest: %s"%self.url)
        else:
            self.assertEqual(mpd_type, "static",
                             "MPD@type must be static for VOD manifest: %s"%self.url)
            duration = root.get('mediaPresentationDuration')
            if self.mediaPresentationDuration is not None:
                self.assertGreaterThan(self.mediaPresentationDuration,
                                       datetime.timedelta(seconds=0),
                                'Invalid MPD@mediaPresentationDuration "{}": {}'.format(duration, self.url))
            else:
                msg = 'If MPD@mediaPresentationDuration is not present, Period@duration must be present: %s'%self.url
                self.assertGreaterThan(len(self.periods), 0, msg)
                for p in self.periods:
                    self.assertIsNotNone(p.duration, msg)

            self.assertIsNone(root.get("minimumUpdatePeriod"),
                              "MPD@minimumUpdatePeriod must not be present for VOD manifest: %s"%self.url)
            self.assertIsNone(root.get("availabilityStartTime"),
                              "MPD@availabilityStartTime must not be present for VOD manifest: %s"%self.url)
        
class DashPeriod(DashElement):
    def __init__(self, period, parent):
        super(DashPeriod, self).__init__(period, parent)
        self.duration = period.get("duration")
        if self.duration is not None:
            self.duration = utils.from_isodatetime(self.duration)
        a = self.element.findall('./dash:AdaptationSet', self.xmlNamespaces)
        self.adaptation_sets = map(lambda a: DashAdaptationSet(a, self), a)
                                   

class DashAdaptationSet(DashElement):
    def __init__(self, adap_set, parent):
        super(DashAdaptationSet, self).__init__(adap_set, parent)
        self.template = None
        self.startNumber = 1
        templates = adap_set.findall('./dash:SegmentTemplate', self.xmlNamespaces)
        if len(templates):
            self.template = templates[0]
            self.startNumber = int(self.template.get('startNumber','1'))
        reps = adap_set.findall('./dash:Representation', self.xmlNamespaces)
        self.representations = map(lambda r: DashRepresentation(r, self), reps)
        prot = adap_set.findall('./dash:ContentProtection', self.xmlNamespaces)
        self.default_KID = None
        for p in prot:
            d = p.get("{{{}}}default_KID".format(self.xmlNamespaces['cenc']))
            if d:
                self.default_KID = d
                break
        if len(prot):
            self.assertIsNotNone(self.default_KID,
                'default_KID cannot be missing for protected stream: {}'.format(self.baseurl))


class DashRepresentation(DashElement):
    def __init__(self, rep, parent):
        super(DashRepresentation, self).__init__(rep, parent)
        self.assertIsNotNone(self.baseurl)
        st = rep.findall('./dash:SegmentTemplate', self.xmlNamespaces)
        if len(st)>0:
            self.template = st[0]
        else:
            self.template = parent.template
        segment_list = rep.findall('./dash:SegmentList', self.xmlNamespaces)
        if segment_list:
            self.segments = list(segment_list[0])
        if self.mode != "odvod":
            self.assertIsNotNone(self.template)
            self.init_url = self.template.get("initialization")
            self.init_url = urlparse.urljoin(self.baseurl, self.init_url)
            self.init_url = self.format_url_template(self.init_url, rep)
            self.media_url = self.template.get("media")
            self.media_url = urlparse.urljoin(self.baseurl, self.media_url)
        else:
            self.init_url = self.baseurl
            self.media_url = self.baseurl

    def format_url_template(self, url, seg_num=0):
        url = url.replace('$RepresentationID$', self.element.get("id"))
        url = url.replace('$Bandwidth$', self.element.get("bandwidth"))
        url = url.replace('$Number$', str(seg_num))
        url = url.replace('$$', '$')
        #TODO: add $Time$
        return url

    
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
            mpd_url = self.from_uri('dash-mpd-v2', manifest=filename, stream='placeholder')
            mpd_url = mpd_url.replace('placeholder', '{directory}')
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
        params = {}
        for idx, option in enumerate(self.cgi_options):
            name, values = option
            value = values[indexes[idx]]
            if value:
                params[name] = value
        # remove pointless combinations of options
        mode = params.get("mode", "mode=live").split('=')[1]
        if mode == "live" and "vod_" in filename:
            return
        if mode != "live":
            if params.has_key("mup"):
                del params["mup"]
            if params.has_key("time"):
                del params["time"]
        cgi = params.values()
        url = self.from_uri('dash-mpd', manifest=filename)
        mpd_url = '{}?{}'.format(url, '&'.join(cgi))
        if mpd_url in tested:
            return
        #print(mpd_url)
        tested.add(mpd_url)
        response = self.app.get(mpd_url)
        mpd = DashManifest(mode, response.xml, mpd_url)
        mpd.validate()

    def test_get_manifest(self):
        """Exhaustive test of every manifest with every combination of options.
        This test is _very_ slow, expect it to take several minutes!"""
        self.setup_media()
        self.logoutCurrentUser()
        pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreater(len(media_files), 0)
        # do a first pass check of every manifest with no CGI options
        for filename, manifest in manifests.manifest.iteritems():
            url = self.from_uri('dash-mpd', manifest=filename)
            response = self.app.get(url)
            mode = 'vod' if 'vod_' in filename else 'live'
            mpd = DashManifest(mode, response.xml, url)
            mpd.validate()

        # do the exhaustive check of every option with every manifest
        total_tests = len(manifests.manifest)
        count = 0
        for param in self.cgi_options:
            total_tests = total_tests * len(param[1])
        for filename, manifest in manifests.manifest.iteritems():
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

    def test_timeshift_buffer_depth(self):
        """Control of MPD@timeShiftBufferDepth using the start parameter"""
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
        self.assertGreater(len(media_files), 0)
        filename = 'hand_made.mpd'
        manifest = manifests.manifest[filename]
        now = datetime.datetime.now(tz=utils.UTC())
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        testcases = [
            ('', today),
            ('today', today),
            ('2019-09-invalid-iso-datetime', today),
            ('now', now),
            ('epoch', datetime.datetime(1970, 1, 1, 0, 0, tzinfo=utils.UTC())),
            ('2009-02-27T10:00:00Z', datetime.datetime(2009,2,27,10,0,0, tzinfo=utils.UTC()) ),
            ('2013-07-25T09:57:31Z', datetime.datetime(2013,7,25,9,57,31, tzinfo=utils.UTC()) ),
        ]
        for option, start_time in testcases:
            baseurl = self.from_uri('dash-mpd-v2', manifest=filename, stream='bbb')
            if option:
                baseurl += '?mode=live&start=' + option
            response = self.app.get(baseurl)
            mpd = DashManifest('live', response.xml, baseurl)
            mpd.validate()
            if option=='now':
                start_time = mpd.publishTime - mpd.timeShiftBufferDepth
            self.assertEqual(mpd.availabilityStartTime, start_time)

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
        pr = drm.PlayReady(self.templates)
        media_files = models.MediaFile.all()
        self.assertGreater(len(media_files), 0)
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
            mpd = DashManifest('vod', response.xml, baseurl)
            mpd.validate()
            for period in mpd.periods:
                self.check_period(period)
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
        self.assertGreater(len(media_files), 0)
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
            mpd = '{{{}}}mpd'.format(DashElement.xmlNamespaces['dash'])
            self.assertEqual(mpd, response.xml.tag.lower())
            mpd = DashManifest("live", response.xml, baseurl)
            mpd.validate()
            for period in mpd.periods:
                self.check_period(period)
        self.progress(total_tests, total_tests)

    def test_get_vod_media_using_on_demand_profile(self):
        """Get VoD segments (on-demand profile)"""
        self.logoutCurrentUser()
        self.setup_media()
        media_files = models.MediaFile.all()
        self.assertGreater(len(media_files), 0)
        chosen = None
        for filename, manifest in manifests.manifest.iteritems():
            baseurl = self.from_uri('dash-mpd-v2', manifest=filename, stream='bbb')
            baseurl += '?mode=odvod'
            response = self.app.get(baseurl)
            if "urn:mpeg:dash:profile:isoff-on-demand:2011" in response.xml.get('profiles'):
                chosen = (baseurl, manifest, response)
                break
        self.assertIsNotNone(chosen)
        baseurl, manifest, response = chosen
        mpd = DashManifest("odvod", response.xml, baseurl)
        mpd.validate()
        for period in mpd.periods:
            self.check_period(period)

    def check_period(self, period):
        for adap_set in period.adaptation_sets:
            if period.mode=="odvod":
                self.check_on_demand_adaptation_set(adap_set)
            else:
                self.check_live_adaptation_set(adap_set)

    def check_live_adaptation_set(self, adap_set):
        for rep in adap_set.representations:
            self.assertIsNotNone(rep.template)
            init_url = rep.format_url_template(rep.init_url)
            mf = self.get_mediafile(init_url)
            moov = self.check_init_segment(init_url, rep, mf)
            num_segments = 5
            decode_time = None
            name = rep.id.lower() + '.mp4'
            mf = models.MediaFile.query(models.MediaFile.name==name).get()
            if mf and adap_set.mode=='vod':
                num_segments = mf.representation.num_segments - 1
                decode_time = 0
            start_number = 1
            if adap_set.mode=='live':
                now = datetime.datetime.now(tz=utils.UTC())
                delta = now - adap_set.mpd.availabilityStartTime
                duration = int(adap_set.template.get('duration'))
                timescale = int(adap_set.template.get('timescale'))
                start_number = long(delta.total_seconds() * timescale / duration)
                num_segments = math.floor(adap_set.mpd.timeShiftBufferDepth.total_seconds() * timescale / duration)
                num_segments = int(num_segments)
                start_number -= num_segments
                if start_number < adap_set.startNumber:
                    num_segments -= adap_set.startNumber - start_number
                    start_number = adap_set.startNumber
                decode_time = (start_number - adap_set.startNumber) * duration
            first=True
            for idx in range(num_segments):
                moof = self.check_media_segment(rep, mf, idx + start_number,
                                                decode_time=decode_time, first=first)
                first=False
                if decode_time is not None:
                    decode_time = moof.traf.tfdt.base_media_decode_time
                    for sample in moof.traf.trun.samples:
                        if sample.duration:
                            decode_time += sample.duration
                        else:
                            decode_time += moov.mvex.trex.default_sample_duration

    def check_on_demand_adaptation_set(self, adap_set):
        for rep in adap_set.representations:
            mf = self.get_mediafile(rep.baseurl)
            decode_time = 0
            for seg_num, item in enumerate(rep.segments):
                if seg_num==0:
                    self.assertTrue(item.tag.endswith('Initialization'))
                    seg_range = item.get("range")
                    self.assertIsNotNone(seg_range)
                    self.check_init_segment(rep.baseurl, rep, mf, seg_range)
                else:
                    self.assertTrue(item.tag.endswith("SegmentURL"))
                    seg_range = item.get("mediaRange")
                    self.assertIsNotNone(seg_range)
                    self.check_media_segment(rep, mf, seg_num,
                                             decode_time=decode_time, seg_range=seg_range)
                    decode_time += mf.representation.segments[seg_num].duration

    def get_mediafile(self, url):
        parts = urlparse.urlparse(url)
        filename = os.path.basename(parts.path)
        name, ext = os.path.splitext(filename)
        name += '.mp4'
        mf = models.MediaFile.query(models.MediaFile.name==name).get()
        if mf is None:
            filename = os.path.dirname(parts.path).split('/')[-1]
            name = filename + '.mp4'
            mf = models.MediaFile.query(models.MediaFile.name==name).get()
        self.assertIsNotNone(mf)
        return mf

    pr_system_id = drm.PlayReady.SYSTEM_ID.replace('-','').lower()

    def check_init_segment(self, init_url, rep, mediafile, seg_range=None):
        if rep.parent.default_KID:
            self.assertIn('_enc', init_url)
        headers = None
        if seg_range is not None:
            headers = {"Range": "bytes={}".format(seg_range)}
        response = self.app.get(init_url, headers=headers)
        src = utils.BufferedReader(None, data=response.body)
        atoms = mp4.Mp4Atom.create(src)
        self.assertGreater(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'ftyp')
        moov = None
        for atom in atoms:
            if atom.atom_type=='moov':
                moov = atom
                break
        self.assertIsNotNone(moov)
        if not '_enc' in init_url:
            return
        try:
            pssh = moov.pssh
            #print pssh
            if pssh.system_id == self.pr_system_id:
                pro = drm.PlayReady.parse_pro(utils.BufferedReader(None, data=pssh.data))
                #print pro
                version = pro['xml'].getroot().get("version")
                self.assertIn(version, ["4.0.0.0", "4.1.0.0", "4.2.0.0"])
        except (AttributeError) as ae:
            if 'moov' in init_url:
                if 'playready' in init_url or 'clearkey' in init_url:
                    self.assertTrue('moov' not in init_url,
                                    'PSSH box should be present in {}\n{:s}'.format(
                                        init_url, ae))
        return moov

    def check_media_segment(self, rep, mediafile, seg_num, decode_time, seg_range=None, first=False):
        if rep.mode=='odvod':
            media_url = rep.format_url_template(rep.baseurl, seg_num)
        else:
            media_url = rep.format_url_template(rep.media_url, seg_num)
        if rep.parent.default_KID:
            self.assertIn('_enc', media_url)
        headers = None
        #print(media_url,decode_time)
        if seg_range is not None:
            headers = {"Range": "bytes={}".format(seg_range)}
        response = self.app.get(media_url, headers=headers)
        src = utils.BufferedReader(None, data=response.body)
        options={}
        if mediafile.representation.encrypted:
            options["iv_size"] = mediafile.representation.iv_size
        atoms = mp4.Mp4Atom.create(src, options=options)
        self.assertGreater(len(atoms), 1)
        self.assertEqual(atoms[0].atom_type, 'moof')
        moof = atoms[0]
        self.assertEqual(moof.mfhd.sequence_number, seg_num)
        if decode_time is not None:
            seg_dt = moof.traf.tfdt.base_media_decode_time
            delta = abs(decode_time - seg_dt)
            tolerance = mediafile.representation.timescale if first else mediafile.representation.timescale/10
            if delta > tolerance:
                raise AssertionError('Decode time {seg_dt:d} should be {dt:d} (delta {delta:d} for segment {num:d} in {url:s}'.format(seg_dt=seg_dt, dt=decode_time, delta=delta, num=seg_num, url=media_url))
        return moof

    def test_request_unknown_media(self):
        url = self.from_uri("dash-media", mode="vod", filename="notfound", segment_num=1, ext="mp4")
        response = self.app.get(url, status=404)

    def test_injected_http_error_codes(self):
        self.setup_media()
        self.logoutCurrentUser()
        media_files = models.MediaFile.all()
        self.assertGreater(len(media_files), 0)
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
        self.assertGreater(len(media_files), 0)
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
                'csrf_token':0,
                'name': 'bbb_v1.mp4',
            }
            for item in ['csrf_token', 'upload_url', 'file_html', 'key', 'blob',
                         'representation']:
                self.assertTrue(response.json.has_key(item))
                expected_result[item] = response.json[item]
            self.assertNotEqual(response.json['csrf_token'], form['csrf_token'])
            self.assertEqual(response.json, expected_result)
        else:
            response.mustcontain('<h2>Upload complete</h2>')
        
        response = self.app.get(url)
        self.assertEqual(response.status_int,200)
        response.mustcontain('bbb_v1.mp4')

if os.environ.get("TESTS"):
    def load_tests(loader, tests, pattern):
        return unittest.loader.TestLoader().loadTestsFromNames(
            os.environ["TESTS"].split(','),
            TestHandlers)

if __name__ == '__main__':
    unittest.main()        
