#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from collections import defaultdict
from collections.abc import Callable
import logging
import os
from pathlib import Path
import subprocess
from typing import Sequence

from dashlive.media.create.media_create_options import MediaCreateOptions

from .creation_result import CreationResult
from .packaged_representation import PackagedRepresentation
from .task import MediaCreationTask

class PackageSourcesTask(MediaCreationTask):
    get_files_fn: Callable[[], list[CreationResult]]

    def __init__(self, options: MediaCreateOptions, get_files: Callable[[], list[CreationResult]]) -> None:
        super().__init__(options)
        self.get_files_fn = get_files

    def run(self) -> Sequence[CreationResult]:
        results: list[PackagedRepresentation] = []
        nothing_to_do: bool = True
        media_files: list[CreationResult] = self.get_files_fn()

        indexes: dict[str, int] = defaultdict(int)  # empty items will be initialized to zero
        dest_file: Path
        for media in media_files:
            idx = indexes[media.content_type] + 1
            indexes[media.content_type] = idx
            dest_file = self.options.destdir / self.destination_filename(media.content_type, idx, False)

            rep_id: str = f"{media.content_type[0]}{idx}"
            er = PackagedRepresentation(
                source=media.filename, content_type=media.content_type, filename=dest_file, file_index=idx,
                track_id=media.track_id, src_track_id=media.track_id, rep_id=rep_id, duration=media.duration)
            if media.content_type != 'video':
                er.role = 'main' if idx == 1 else 'alternate'
            if media.content_type == "text":
                er.segment_duration = self.options.segment_duration * 2
                # ! ugly hack !
                # for some reason, when a duration is provided to MP4Box, it only
                # produces a stream with 2/3 of the requested duration
                er.duration = self.options.duration * 1.5 + self.options.segment_duration

            nothing_to_do = nothing_to_do and dest_file.exists()
            results.append(er)

        if nothing_to_do:
            return results

        self.package_sources(results)

        return results

    def package_sources(self, source_files: list[PackagedRepresentation]) -> None:
        tmpdir: Path = self.options.destdir / "dash"
        tmpdir.mkdir(parents=True, exist_ok=True)
        bs_switching: str = 'inband' if self.options.avc3 else 'merge'
        mp4box_args: list[str] = [
            "MP4Box",
            "-dash", str(self.options.segment_duration * self.options.timescale),
            "-frag", str(self.options.segment_duration * self.options.timescale),
            "-dash-scale", str(self.options.timescale),
            "-rap",
            "-fps", str(self.options.framerate),
            "-frag-rap",
            "-profile", "live",
            "-profile-ext", "urn:dvb:dash:profile:dvb-dash:2014",
            "-bs-switching", bs_switching,
            "-lang", self.options.language,
            "-segment-ext", "mp4",
            "-segment-name", 'dash_$RepresentationID$_$Number%03d$$Init=init$',
            "-out", "manifest",
        ]
        for src in source_files:
            mp4box_args.append(src.mp4box_name())

        logging.debug('mp4box_args: %s', mp4box_args)
        cwd: str = os.getcwd()
        os.chdir(tmpdir)
        subprocess.check_call(mp4box_args)
        os.chdir(cwd)
        if self.options.verbose:
            subprocess.call(["ls", "-lR", tmpdir])

        for source in source_files:
            prefix = str(tmpdir / f'dash_{source.rep_id}_')
            dest_name: str = self.destination_filename(source.content_type, source.file_index, False)
            dest_file: Path = self.options.destdir / dest_name
            if dest_file.exists():
                logging.debug('File %s exists, skipping generation', dest_file)
                continue
            moov: Path = tmpdir / f'dash_{source.rep_id}_init.mp4'
            logging.debug('try init filename: %s', moov)
            if not moov.exists():
                moov = tmpdir / 'dash_1_init.mp4'
                logging.debug('try init filename: %s', moov)
            if not moov.exists():
                moov = tmpdir / 'manifest_set1_init.mp4'
                logging.debug('try init filename: %s', moov)
            if not moov.exists():
                moov = Path(prefix + 'init.mp4')
                logging.debug('try init filename: %s', moov)
            if not moov.exists():
                logging.error('Failed to find init segment for representation %s: %s',
                              source.rep_id, prefix)
                continue
            logging.debug('Check for file: "%s"', dest_file)
            self.create_file_from_fragments(dest_file, moov, prefix)
            if source.src_track_id is not None and source.src_track_id != source.track_id:
                self.modify_mp4_file(dest_file, source.track_id, self.options.language)
