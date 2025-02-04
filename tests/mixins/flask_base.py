#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import binascii
from datetime import timedelta
from importlib import metadata
import json
import logging
import os
from pathlib import Path
from typing import Any, ClassVar, Optional, cast

from bs4 import element
import flask
from pyfakefs.fake_filesystem_unittest import TestCaseMixin as PyfakefsTestCaseMixin
from werkzeug.test import TestResponse

from dashlive.drm.playready import PlayReady
from dashlive.mpeg import mp4
from dashlive.mpeg.dash.representation import Representation
from dashlive.server import models
from dashlive.server.app import create_app
from dashlive.server.requesthandler.user_management import LoginResponseJson
from dashlive.utils.date_time import from_isodatetime

from .async_flask_testing import AsyncFlaskTestCase
from .context_filter import ContextFilter
from .mixin import TestCaseMixin as DashTestCaseMixin
from .stream_fixtures import MultiPeriodStreamFixture, StreamFixture, BBB_FIXTURE

class FlaskTestBase(DashTestCaseMixin, AsyncFlaskTestCase, PyfakefsTestCaseMixin):
    SRC_DIR: ClassVar[Path] = Path(__file__).parent.parent.parent.absolute()
    REAL_FIXTURES_PATH: ClassVar[Path] = Path(__file__).parent.parent / "fixtures"
    TEMPLATES_PATH: ClassVar[Path] = SRC_DIR / "templates"
    REAL_STATIC_PATH: ClassVar[Path] = SRC_DIR / "static"
    INDEX_PAGE: ClassVar[str] = """
<!doctype html>
<html lang="en">
<body>
  <div id="app"></div>
</body>
</html>
"""
    ADMIN_USER: ClassVar[str] = 'admin'
    ADMIN_EMAIL: ClassVar[str] = 'admin@dashlive.unit.test'
    ADMIN_PASSWORD: ClassVar[str] = r'suuuperSecret!'
    ENABLE_WSS: ClassVar[bool] = False
    STD_USER: ClassVar[str] = 'user'
    STD_EMAIL: ClassVar[str] = 'user@dashlive.unit.test'
    STD_PASSWORD: ClassVar[str] = r'pa55word'
    MEDIA_USER: ClassVar[str] = 'media'
    MEDIA_EMAIL: ClassVar[str] = 'media@dashlive.unit.test'
    MEDIA_PASSWORD: ClassVar[str] = r'm3d!a'
    LOG_LEVEL: ClassVar[int] = logging.WARNING
    log_context: ClassVar[Optional[ContextFilter]] = None
    checked_urls: ClassVar[set[str]]

    FIXTURES_PATH: Path
    STATIC_PATH: Path
    TEMPLATES_PATH: Path

    current_url: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.checked_urls = set()
        cls.log_context = ContextFilter({'url'})
        format = r"%(asctime)s %(levelname)-8s:%(filename)s@%(lineno)d: %(message)s"
        logging.basicConfig(level=cls.LOG_LEVEL, format=format,
                            datefmt='%d-%m-%y %H:%M:%S')
        formatter = logging.Formatter(format + r"\n%(url)s", defaults={"url": ""})
        console = logging.StreamHandler()
        console.setLevel(cls.LOG_LEVEL)
        console.setFormatter(formatter)
        dash_log = logging.getLogger('DashValidator')
        dash_log.addFilter(cls.log_context)
        dash_log.setLevel(cls.LOG_LEVEL)
        dash_log.addHandler(console)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.log_context:
            dash_log = logging.getLogger('DashValidator')
            dash_log.removeFilter(cls.log_context)
            cls.log_context = None
        logging.disable(logging.NOTSET)
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.FIXTURES_PATH = self.REAL_FIXTURES_PATH
        self.STATIC_PATH = self.REAL_STATIC_PATH

    def create_app(self) -> flask.Flask:
        config = {
            'BLOB_FOLDER': str(self.FIXTURES_PATH),
            'DASH': {
                'ALLOWED_DOMAINS': '*',
                'CSRF_SECRET': 'test.csrf.secret',
                'DEFAULT_ADMIN_USERNAME': self.ADMIN_USER,
                'DEFAULT_ADMIN_PASSWORD': self.ADMIN_PASSWORD,
            },
            'UPLOAD_FOLDER': '/uploads',
            'SECRET_KEY': 'cookie.secret',
            'SQLALCHEMY_DATABASE_URI': "sqlite:///:memory:",
            'TESTING': True,
            'LOG_LEVEL': 'critical',
            'PREFERRED_URL_SCHEME': 'http',
        }
        app: flask.Flask = create_app(
            config=config, create_default_user=False, wss=self.ENABLE_WSS)
        with app.app_context():
            admin = models.User(
                username=self.ADMIN_USER,
                email=self.ADMIN_EMAIL,
                password=models.User.hash_password(self.ADMIN_PASSWORD),
                groups_mask=models.Group.ADMIN,
                must_change=False,
            )
            models.db.session.add(admin)
            std_user = models.User(
                username=self.STD_USER,
                email=self.STD_EMAIL,
                password=models.User.hash_password(self.STD_PASSWORD),
                groups_mask=models.Group.USER,
                must_change=False,
            )
            models.db.session.add(std_user)
            media_user = models.User(
                username=self.MEDIA_USER,
                email=self.MEDIA_EMAIL,
                password=models.User.hash_password(self.MEDIA_PASSWORD),
                groups_mask=(models.Group.USER + models.Group.MEDIA),
                must_change=False,
            )
            models.db.session.add(media_user)
            models.User.get_guest_user()
            models.db.session.commit()
        self.setup_fake_fs(app)
        return app

    @staticmethod
    def find_site_packages() -> Path:
        """
        Find the site-packages directory for the current environment
        """
        for pkg in ["werkzeug", "flask", "sqlalchemy"]:
            files: list[os.PathLike[str]] = [f.locate() for f in metadata.files(pkg) if str(f).endswith('METADATA')]
            for name in files:
                if 'site-packages' not in str(name).lower():
                    continue
                pkg_dir: Path = Path(name).parent
                while pkg_dir.parent != Path():
                    if pkg_dir.name.lower() == 'site-packages':
                        return pkg_dir
                    pkg_dir = pkg_dir.parent
        raise FileNotFoundError("Cannot find site-packages directory")

    def setup_fake_fs(self, app: flask.Flask) -> None:
        site_packages = self.find_site_packages()
        drive: str = self.REAL_FIXTURES_PATH.drive
        self.setUpPyfakefs()
        self.FIXTURES_PATH = Path(f"{drive}/fixtures")
        self.STATIC_PATH = Path(f"{drive}/static")
        blob_folder = Path(f"{drive}/media/blobs")
        # Flask needs to be able to read metadata files from werkzeug at runtime
        self.fs.add_real_directory(site_packages, read_only=True, lazy_read=True)
        self.fs.add_real_directory(
            self.REAL_FIXTURES_PATH, read_only=True, lazy_read=True, target_path=self.FIXTURES_PATH)
        self.fs.add_real_directory(self.TEMPLATES_PATH, read_only=True, lazy_read=True)
        self.fs.create_dir(f"{self.STATIC_PATH}")
        self.fs.create_dir(f"{self.STATIC_PATH / 'html'}")
        self.fs.create_file(
            f"{self.STATIC_PATH / 'html' / 'index.html'}", encoding="utf-8", contents=self.INDEX_PAGE)
        uploads_dir: str = f"{drive}/uploads"
        self.fs.create_dir(uploads_dir)
        app.config.update(
            BLOB_FOLDER=str(blob_folder),
            STATIC_FOLDER=str(self.STATIC_PATH),
            UPLOAD_FOLDER=uploads_dir)

    def setup_media(self, with_subs=False) -> None:
        self.setup_media_fixture(BBB_FIXTURE)

    def setup_content_types(self) -> None:
        content_types: list[str] = [
            "application", "video", "audio", "text", "image",
        ]
        with self.app.app_context():
            for name in content_types:
                ct = models.ContentType.get(name=name)
                if ct is None:
                    ct = models.ContentType(name=name)
                    models.db.session.add(ct)
            models.db.session.commit()

    def setup_media_fixture(self, fixture: StreamFixture, with_subs=False) -> None:
        stream: models.Stream | None = models.Stream.get(directory=fixture.name)
        if stream is not None:
            return
        self.setup_content_types()
        blob_folder: Path = Path(self.app.config['BLOB_FOLDER'])
        self.fs.add_real_directory(
            self.REAL_FIXTURES_PATH / fixture.name, read_only=True, lazy_read=False,
            target_path=(blob_folder / fixture.name))
        # print('add real directory', self.REAL_FIXTURES_PATH / fixture.name, blob_folder / fixture.name)
        stream = models.Stream(
            title=fixture.title,
            directory=fixture.name,
            marlin_la_url=f"ms3://localhost/marlin/{fixture.name}",
            playready_la_url=PlayReady.TEST_LA_URL
        )
        fixture_files: list[str] = []
        patten: str = f"{fixture.name}_[av]*.mp4"
        if with_subs:
            patten = f"{fixture.name}_[avt]*.mp4"
        fixtures_dir: Path = self.FIXTURES_PATH / fixture.name
        for item in fixtures_dir.glob(patten):
            fixture_files.append(item.stem)
        fixture_files.sort()
        media_files: list[models.MediaFile] = []
        for name in fixture_files:
            mf = self.add_blob_and_media_file(fixture, stream, name)
            media_files.append(mf)
            if stream.timing_reference is None and '_v' in name:
                stream.timing_reference = mf.as_stream_timing_reference()
        with self.app.app_context():
            models.db.session.add(stream)
            for mf in media_files:
                models.db.session.add(mf.blob)
                models.db.session.add(mf)
            models.db.session.commit()
        self.add_media_keys()

    def add_media_keys(self) -> None:
        with self.app.app_context():
            kids: set[bytes] = set()
            self.assertGreaterThan(models.MediaFile.count(), 0)
            for mf in models.MediaFile.all():
                r = mf.representation
                assert r is not None
                if not r.encrypted:
                    continue
                for kid in r.kids:
                    if kid.raw in kids:
                        continue
                    key = binascii.b2a_hex(PlayReady.generate_content_key(kid.raw))
                    keypair: models.Key | None = models.Key.get(hkid=kid.hex)
                    if keypair is None:
                        keypair = models.Key(hkid=kid.hex, hkey=key, computed=True)
                        models.db.session.add(keypair)
                    kids.add(kid.raw)
            models.db.session.commit()

    def add_blob_and_media_file(self,
                                fixture: StreamFixture,
                                stream: models.Stream,
                                name: str) -> models.MediaFile:
        filename = f"{name}.mp4"
        src_file = self.FIXTURES_PATH / fixture.name / filename
        if '_v' in name:
            content_type = 'video'
        elif '_a' in name:
            content_type = 'audio'
        else:
            content_type = 'text'

        blob = models.Blob(
            filename=filename,
            created=from_isodatetime("2022-09-01T12:23:00Z"),
            size=src_file.stat().st_size,
            sha1_hash=str(src_file),
            content_type=content_type,
            auto_delete=False)

        js_filename = self.FIXTURES_PATH / fixture.name / f'rep-{name}.json'
        rep: Representation | None = None
        if js_filename.exists():
            with js_filename.open('rt', encoding='utf-8') as src:
                rep_js = json.load(src)
            if rep_js['version'] == Representation.VERSION:
                rep = Representation(**rep_js)
        if rep is None:
            print(f'Creating Representation cache: {js_filename}')
            with src_file.open(mode="rb", buffering=16384) as src:
                atoms = mp4.Mp4Atom.load(src)
            rep = Representation.load(filename, atoms)
            rep_js = rep.toJSON(pure=True)
            with js_filename.open('wt', encoding='utf-8') as dest:
                json.dump(rep_js, dest, indent=2)
        self.assertIsNotNone(rep)
        self.assertIsInstance(rep, Representation)
        encrypted = name.endswith('_enc')
        self.assertEqual(encrypted, rep.encrypted)
        self.assertAlmostEqual(
            rep.mediaDuration,
            fixture.media_duration * rep.timescale,
            delta=(rep.timescale / 5.0),
            msg='Invalid duration for {}. Expected {} got {}'.format(
                filename, fixture.media_duration * rep.timescale,
                rep.mediaDuration))

        mf = models.MediaFile(
            name=name,
            stream=stream,
            bitrate=rep.bitrate,
            content_type=rep.content_type,
            codec_fourcc=rep.codecs.split('.')[0],
            track_id=rep.track_id,
            encrypted=rep.encrypted,
            blob=blob)
        mf.set_representation(rep)

        return mf

    def setup_multi_period_stream(self,
                                  fixture: MultiPeriodStreamFixture
                                  ) -> None:
        for period in fixture.periods:
            self.setup_media_fixture(period.fixture)
        with self.app.app_context():
            mps = models.MultiPeriodStream(
                name=fixture.name, title=fixture.title)
            models.db.session.add(mps)
            for idx, period in enumerate(fixture.periods, start=1):
                stream = models.Stream.get(directory=period.fixture.name)
                assert stream is not None
                start: int = period.fixture.segment_duration * period.start
                duration: int = period.fixture.media_duration
                duration -= start
                duration -= period.end * period.fixture.segment_duration
                prd = models.Period(
                    pid=period.pid, parent=mps, ordering=idx, stream=stream,
                    start=timedelta(seconds=start),
                    duration=timedelta(seconds=duration))
                models.db.session.add(prd)
                for trk in period.tracks:
                    ct = models.ContentType.get(name=trk.ttype)
                    assert ct is not None
                    adp = models.AdaptationSet(
                        period=prd, track_id=trk.tid,
                        role=trk.role.value,
                        content_type=ct)
                    models.db.session.add(adp)
                models.db.session.add(adp)
            models.db.session.commit()
            self.assertEqual(
                timedelta(seconds=fixture.media_duration),
                mps.total_duration())

    def change_track_id(self, name: str, track_id: int) -> None:
        with self.app.app_context():
            mf = models.MediaFile.get(name='bbb_t1')
            if mf is None:
                print(f'Failed to find MediaFile(name={name})')
                return
            if mf.representation.track_id != track_id:
                new_filename = self.FIXTURES_PATH / f'{name}_{track_id}.mp4'
                print('Creating new track', new_filename)
                mf.modify_media_file(
                    new_filename=new_filename,
                    modify_atoms=lambda atom: models.MediaFile._set_track_id(
                        atom, track_id))

    def tearDown(self):
        self.logout_user()
        if hasattr(DashTestCaseMixin, "_orig_assert_true"):
            DashTestCaseMixin._assert_true = DashTestCaseMixin._orig_assert_true
            del DashTestCaseMixin._orig_assert_true
        models.db.session.remove()
        models.db.drop_all()

    def login_user(self, username: str | None = None,
                   password: str | None = None,
                   is_admin: bool = False,
                   rememberme: bool = False) -> LoginResponseJson:
        if is_admin:
            if username is None:
                username = self.ADMIN_USER
                password = self.ADMIN_PASSWORD
        else:
            if username is None:
                username = self.STD_USER
                password = self.STD_PASSWORD
        login_url: str = flask.url_for('api-login')
        response = self.client.post(
            login_url,
            json={
                'username': username,
                'password': password,
                'rememberme': rememberme,
            },
            content_type='application/json')
        return cast(LoginResponseJson, response.json)

    def logout_user(self) -> TestResponse:
        logout_url: str = flask.url_for('logout')
        return self.client.get(logout_url)

    def assertNotAuthorized(self, response, ajax: int) -> None:
        if ajax:
            self.assertEqual(response.status_code, 401)
            return
        self.assertEqual(response.status_code, 200)
        self.assertIn('This page requires you to log in', response.text)

    def check_form(self, form: element.Tag, expected: dict[str, Any]) -> str | None:
        """
        Check that the supplied HTML form has the expected fields and values
        """
        csrf_token: str | None = None
        for input_field in form.find_all('input'):
            name = input_field.get('name')
            if name == 'csrf_token':
                self.assertEqual(
                    input_field.get('type'),
                    'hidden')
                csrf_token = input_field.get('value')
                continue
            if expected[name] is None:
                self.assertEqual("", input_field.get('value', ""))
            elif isinstance(expected[name], bool):
                if expected[name] is True:
                    msg = f'Expected "{name}" field to be checked'
                    self.assertIsNotNone(input_field.get('checked'), msg=msg)
                else:
                    msg = f'Expected "{name}" field to not be checked'
                    self.assertIsNone(input_field.get('checked'), msg=msg)
            else:
                self.assertEqual(expected[name], input_field.get('value'))
        return csrf_token
