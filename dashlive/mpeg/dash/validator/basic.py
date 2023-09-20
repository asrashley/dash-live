#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import argparse
import logging
import math
import traceback

from .validator import DashValidator
from .exceptions import ValidationException
from .options import ValidatorOptions
from .representation_info import RepresentationInfo
from .requests_http_client import RequestsHttpClient

class BasicDashValidator(DashValidator):
    def __init__(self, url: str, options: ValidatorOptions) -> None:
        super().__init__(
            url,
            RequestsHttpClient(options),
            options=options)
        self.representations = {}
        self.url = url

    def get_representation_info(self, rep) -> RepresentationInfo | None:
        try:
            return self.representations[rep.unique_id()]
        except KeyError:
            pass
        timescale = 1
        if rep.mode == 'odvod':
            if rep.segmentBase is not None:
                timescale = rep.segmentBase.timescale
        elif rep.segmentTemplate is not None:
            timescale = rep.segmentTemplate.timescale
        num_segments = None
        if rep.segmentTemplate and rep.segmentTemplate.segmentTimeline is not None:
            num_segments = len(rep.segmentTemplate.segmentTimeline.segments)
        else:
            duration = rep.parent.parent.duration
            if duration is None:
                duration = rep.mpd.mediaPresentationDuration
            if duration is not None and rep.segmentTemplate:
                seg_dur = rep.segmentTemplate.duration
                num_segments = int(
                    math.floor(duration.total_seconds() * timescale / seg_dur))
        return RepresentationInfo(encrypted=self.options.encrypted,
                                  ivsize=self.options.ivsize,
                                  timescale=timescale,
                                  num_segments=num_segments)

    def set_representation_info(self, representation, info):
        self.representations[representation.unique_id()] = info

    @classmethod
    def main(cls):
        parser = argparse.ArgumentParser(
            description='DASH live manifest validator')
        parser.add_argument('-e', '--encrypted', action='store_true', dest='encrypted',
                            help='Stream is encrypted')
        parser.add_argument('-s', '--save',
                            help='save all fragments into <dest>',
                            action='store_true')
        parser.add_argument('--pretty',
                            help='pretty print XML before validation',
                            action='store_true')
        parser.add_argument('-d', '--dest',
                            help='directory to store results',
                            required=False)
        parser.add_argument('--prefix',
                            help='filename prefix to use when storing media files',
                            required=False)
        parser.add_argument('--duration',
                            help='Maximum duration (in seconds)',
                            type=int,
                            required=False)
        parser.add_argument('--ivsize',
                            help='IV size (in bits or bytes)',
                            type=int,
                            default=64,
                            required=False)
        parser.add_argument('-v', '--verbose', '--debug',
                            dest='verbose',
                            action='count',
                            help='increase verbosity',
                            default=0)
        parser.add_argument(
            'manifest',
            help='URL or filename of manifest to validate')
        args = parser.parse_args(namespace=ValidatorOptions())
        # FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s\n  [%(url)s]"
        FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
        logging.basicConfig(format=FORMAT)
        args.log = logging.getLogger('DashValidator')
        if args.verbose > 0:
            args.log.setLevel(logging.DEBUG)
            if args.verbose > 1:
                logging.getLogger('mp4').setLevel(logging.DEBUG)
                logging.getLogger('fio').setLevel(logging.DEBUG)
        if args.ivsize is not None and args.ivsize > 16:
            args.ivsize = args.ivsize // 8
        bdv = cls(args.manifest, args)
        bdv.load()
        if args.dest:
            bdv.save_manifest()
        done = False
        while not done:
            if bdv.manifest.mpd_type != 'dynamic' or args.duration:
                done = True
            try:
                bdv.validate()
                if bdv.manifest.mpd_type == 'dynamic' and not done:
                    bdv.sleep()
                    bdv.load()
            except (AssertionError, ValidationException) as err:
                args.log.error(err)
                traceback.print_exc()
                if args.dest:
                    bdv.save_manifest()
                    filename = bdv.output_filename('error.txt', makedirs=True)
                    with open(filename, 'w') as err_file:
                        err_file.write(str(err) + '\n')
                        traceback.print_exc(file=err_file)
