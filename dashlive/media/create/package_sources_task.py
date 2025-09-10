#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import logging
import os
from pathlib import Path
import subprocess
from typing import Sequence

from .creation_result import CreationResult
from .encoding_parameters import BITRATE_PROFILES, VideoEncodingParameters
from .encoded_representation import EncodedRepresentation
from .task import MediaCreationTask

class PackageSourcesTask(MediaCreationTask):
    def run(self) -> Sequence[CreationResult]:
        results: list[EncodedRepresentation] = []
        ladder: list[VideoEncodingParameters] = BITRATE_PROFILES[self.options.bitrate_profile]
        nothing_to_do: bool = True

        src_file: Path
        dest_file: Path
        for idx, br in enumerate(ladder, start=1):
            bitrate: int = br[2]
            if self.options.max_bitrate > 0 and bitrate > self.options.max_bitrate:
                break

            src_file = self.options.destdir / f'{bitrate}' / f'{self.options.prefix}.mp4'
            dest_file = self.options.destdir / self.destination_filename('v', idx, False)
            results.append(EncodedRepresentation(
                source=src_file, content_type='video', filename=dest_file, file_index=idx, track_id=1,
                src_track_id=1, rep_id=f"v{idx}", duration=self.options.duration))
            nothing_to_do = nothing_to_do and dest_file.exists()

        # Add main audio track
        src_file = self.options.destdir / f'{ladder[0][2]}' / f'{self.options.prefix}.mp4'
        dest_file = self.options.destdir / self.destination_filename('a', 1, False)
        results.append(EncodedRepresentation(
            source=src_file, filename=dest_file, content_type='audio', track_id=2, file_index=1, role="main",
            src_track_id=2, rep_id="a1", duration=self.options.duration))
        nothing_to_do = nothing_to_do and dest_file.exists()

        # alternate audio track
        if self.options.surround:
            dest_file = self.options.destdir / self.destination_filename('a', 2, False)
            nothing_to_do = nothing_to_do and dest_file.exists()
            results.append(EncodedRepresentation(
                source=src_file, filename=dest_file, content_type='audio', track_id=3, file_index=2,
                src_track_id=3, role="alternate", rep_id="a2", duration=self.options.duration))

        if self.options.subtitles:
            src: Path = Path(self.options.subtitles)
            ttml_file: Path = src
            if src.suffix != '.ttml':
                ttml_file = self.options.destdir / Path(self.options.subtitles).with_suffix('.ttml').name
            nothing_to_do = nothing_to_do and ttml_file.exists()
            dest_file = self.options.destdir / self.destination_filename('t', 1, False)
            nothing_to_do = nothing_to_do and dest_file.exists()
            dest_track_id: int = 4 if self.options.surround else 3
            # ! ugly hack !
            # for some reason, when a duration is provided to MP4Box, it only
            # produces a stream with 2/3 of the requested duration
            results.append(EncodedRepresentation(
                source=ttml_file, filename=dest_file, content_type='text', src_track_id=1, track_id=dest_track_id,
                file_index=1, role="main", rep_id="t1",
                duration=self.options.duration * 1.5 + self.options.segment_duration,
                segment_duration=self.options.segment_duration * 2))

        if nothing_to_do:
            return results

        self.package_sources(results)

        return results

    def package_sources(self, source_files: list[EncodedRepresentation]) -> None:
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
