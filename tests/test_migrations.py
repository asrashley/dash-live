#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import logging
from pathlib import Path
import unittest
from unittest.mock import ANY, call, patch

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection

from dashlive.server import models
from dashlive.server.models.migrations.unique_track_ids import EnsureTrackIdsAreUnique

from .mixins.flask_base import FlaskTestBase
from .mixins.stream_fixtures import BBB_FIXTURE

class DataMigrationTests(FlaskTestBase):
    def test_aac_audio_track_needs_changing(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 1,
            "bbb_a1_enc": 1,
            "bbb_a2": 2,
            "bbb_a2_enc": 2,
            "bbb_t1": 3,
        }
        new_files: list[str] = [
            'bbb_a1_04.mp4',
            'bbb_a1_enc_04.mp4',
        ]
        self.check_track_ids_are_unique(track_mapping, new_files, True)

    def test_aac_audio_track_change_fails(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 1,
            "bbb_a1_enc": 1,
            "bbb_a2": 2,
            "bbb_a2_enc": 2,
            "bbb_t1": 3,
        }
        new_files: list[str] = [
            'bbb_a1_04.mp4',
        ]
        self.check_track_ids_are_unique(track_mapping, new_files, False)

    def test_eac3_audio_track_needs_changing(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 2,
            "bbb_a1_enc": 2,
            "bbb_a2": 2,
            "bbb_a2_enc": 2,
            "bbb_t1": 3,
        }
        new_files: list[str] = [
            'bbb_a2_04.mp4',
            'bbb_a2_enc_04.mp4',
        ]
        self.check_track_ids_are_unique(track_mapping, new_files, True)

    def test_text_audio_track_needs_changing(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 2,
            "bbb_a1_enc": 2,
            "bbb_a2": 3,
            "bbb_a2_enc": 3,
            "bbb_t1": 1,
        }
        new_files: list[str] = [
            'bbb_t1_04.mp4',
        ]
        self.check_track_ids_are_unique(track_mapping, new_files, True)

    def test_no_tracks_needs_changing(self) -> None:
        track_mapping: dict[str, int] = {
            "bbb_v6": 1,
            "bbb_v6_enc": 1,
            "bbb_v7": 1,
            "bbb_v7_enc": 1,
            "bbb_a1": 2,
            "bbb_a1_enc": 2,
            "bbb_a2": 3,
            "bbb_a2_enc": 3,
            "bbb_t1": 4,
        }
        new_files: list[str] = []
        self.check_track_ids_are_unique(track_mapping, new_files, True)

    def check_track_ids_are_unique(
            self,
            track_mapping: dict[str, int],
            new_files: list[str],
            success: bool) -> None:
        self.setup_media_fixture(BBB_FIXTURE, with_subs=True)
        with self.app.app_context():
            for name in track_mapping.keys():
                media = models.MediaFile.get(name=name)
                self.assertIsNotNone(media)
                mrep = media.representation
                self.assertIsNotNone(
                    mrep,
                    msg=f'representation data missing from fixture {name}')
                mrep.track_id = track_mapping[name]
                media.track_id = track_mapping[name]
                media.set_representation(mrep)
            models.db.session.commit()
        blob_folder = self.fixtures_folder
        with self.app.app_context():
            session = models.db.session
            with patch('dashlive.server.models.MediaFile.modify_media_file') as mock_modify:
                mock_modify.return_value = success
                migration = EnsureTrackIdsAreUnique(blob_folder)
                # migration.log.info = lambda fmt, *args: print(fmt % args)
                # migration.log.debug = lambda fmt, *args: print(fmt % args)
                # migration.log.warning = lambda fmt, *args: print(fmt % args)
                errors: list[str] = []
                migration.log.errors = lambda fmt, *args: errors.append(fmt % args)
                migration.upgrade(session)
                if success:
                    self.assertListEqual(errors, [])
                calls: list[call] = [
                    call(session=session, blob_folder=blob_folder,
                         new_filename=(self.fixtures_folder / BBB_FIXTURE.name / name),
                         modify_atoms=ANY) for name in new_files]
                if not calls:
                    mock_modify.assert_not_called()
                else:
                    mock_modify.assert_has_calls(calls, any_order=True)

class AlembicMigrationTests(unittest.TestCase):
    @staticmethod
    def fixture_filename(name: str | Path) -> Path:
        """returns absolute file path of the given fixture"""
        return Path(__file__).parent / "fixtures" / name

    @classmethod
    def load_fixture(cls, connection: Connection, filename: str) -> None:
        """
        Load the specified SQL file into the database
        """
        sql_filename: Path = cls.fixture_filename(filename)
        with sql_filename.open('rt', encoding="utf-8") as src:
            sql: str = src.read()
        for line in sql.split(';\n'):
            while line and line[0] in [' ', '\r', '\n']:
                line = line[1:]
            if not line:
                continue
            if line in ['BEGIN TRANSACTION', 'COMMIT', 'PRAGMA foreign_keys=OFF']:
                continue
            # print(f'"{line}"')
            connection.execute(text(line))

    def test_migrate_from_v1_5(self) -> None:
        connect_str = "sqlite:///:memory:"
        engine: Engine = create_engine(connect_str, echo=False)
        basedir: Path = Path(__file__).parent.parent
        alembic_cfg = Config(basedir / "alembic.ini")
        with engine.begin() as connection:
            alembic_cfg.attributes['connection'] = connection
            self.load_fixture(connection, "db-v1.5.sql")
            command.stamp(alembic_cfg, "base")
            command.upgrade(alembic_cfg, "head")

    def test_migrate_from_v2_5(self) -> None:
        connect_str = "sqlite:///:memory:"
        engine: Engine = create_engine(connect_str, echo=False)
        basedir: Path = Path(__file__).parent.parent
        alembic_cfg = Config(basedir / "alembic.ini")
        with engine.begin() as connection:
            alembic_cfg.attributes['connection'] = connection
            self.load_fixture(connection, "db-v2.5.sql")
            command.stamp(alembic_cfg, "e3cdc4f4779b")
            command.upgrade(alembic_cfg, "head")

    def test_migrate_from_v2_5_with_missing_stamp(self) -> None:
        """
        Test what happens with a migration from v2.5 where the database
        was missing its stamp
        """
        connect_str = "sqlite:///:memory:"
        engine: Engine = create_engine(connect_str, echo=False)
        basedir: Path = Path(__file__).parent.parent
        alembic_cfg = Config(basedir / "alembic.ini")
        with engine.begin() as connection:
            alembic_cfg.attributes['connection'] = connection
            self.load_fixture(connection, "db-v2.5.sql")
            command.stamp(alembic_cfg, "base")
            command.upgrade(alembic_cfg, "head")

    def test_migrate_from_v2_6(self) -> None:
        connect_str = "sqlite:///:memory:"
        engine: Engine = create_engine(connect_str, echo=False)
        basedir: Path = Path(__file__).parent.parent
        alembic_cfg = Config(basedir / "alembic.ini")
        with engine.begin() as connection:
            alembic_cfg.attributes['connection'] = connection
            self.load_fixture(connection, "db-v2.5.sql")
            command.stamp(alembic_cfg, "d5bd6b74a282")
            command.upgrade(alembic_cfg, "head")

    def test_migrate_from_v2_6_with_missing_stamp(self) -> None:
        connect_str = "sqlite:///:memory:"
        engine: Engine = create_engine(connect_str, echo=False)
        basedir: Path = Path(__file__).parent.parent
        alembic_cfg = Config(basedir / "alembic.ini")
        with engine.begin() as connection:
            alembic_cfg.attributes['connection'] = connection
            self.load_fixture(connection, "db-v2.6.sql")
            command.stamp(alembic_cfg, "base")
            command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    log = logging.getLogger('dashlive.server.models.migrations')
    log.setLevel(logging.DEBUG)
    unittest.main()
