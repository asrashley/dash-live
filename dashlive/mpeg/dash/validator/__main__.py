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
import requests
import traceback

from lxml import etree as ET

from dashlive.testcase.mixin import HideMixinsFilter, TestCaseMixin

from .validator import DashValidator
from .exceptions import ValidationException
from .options import ValidatorOptions
from .representation_info import RepresentationInfo

class HttpResponse(TestCaseMixin):
    def __init__(self, response):
        self.response = response
        self.status_int = self.status_code = response.status_code
        self._xml = None
        self.headers = response.headers
        self.headerlist = list(response.headers.keys())
        if response.ok:
            self.status = 'OK'
        else:
            self.status = response.reason

    @property
    def xml(self):
        if self._xml is None:
            self._xml = ET.fromstring(self.response.text)
        return self._xml

    @property
    def forms(self, id):
        raise Exception("Not implemented")

    @property
    def json(self):
        return self.response.json

    @property
    def body(self):
        return self.response.content

    def get_data(self, as_text: bool) -> bytes | str:
        if as_text:
            return self.response.text
        return self.response.content

    def mustcontain(self, *strings):
        for text in strings:
            self.checkIn(text, self.response.text)

    def warning(self, fmt, *args):
        logging.getLogger(__name__).warning(fmt, *args)


class RequestsHttpClient(TestCaseMixin):
    """
    Implements HttpClient protocol using the requests library
    """

    def __init__(self):
        self.session = requests.Session()

    def get(self, url, headers=None, params=None, status=None, xhr=False):
        try:
            self.log.debug('GET %s', url)
        except AttributeError:
            print('GET %s' % (url))
        if xhr:
            if headers is None:
                headers = {'X-REQUESTED-WITH': 'XMLHttpRequest'}
            else:
                h = {'X-REQUESTED-WITH': 'XMLHttpRequest'}
                h.update(headers)
                headers = h
        rv = HttpResponse(
            self.session.get(
                url,
                data=params,
                headers=headers))
        if status is not None:
            self.checkEqual(rv.status_code, status)
        return rv


class BasicDashValidator(DashValidator):
    def __init__(self, url, options):
        super().__init__(
            url,
            RequestsHttpClient(),
            options=options)
        self.representations = {}
        self.url = url

    def get_representation_info(self, rep) -> RepresentationInfo:
        try:
            return self.representations[rep.unique_id()]
        except KeyError:
            pass
        if rep.mode == 'odvod':
            timescale = rep.segmentBase.timescale
        elif rep.segmentTemplate is not None:
            timescale = rep.segmentTemplate.timescale
        else:
            timescale = 1
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
                                  iv_size=self.options.ivsize,
                                  timescale=timescale,
                                  num_segments=num_segments)

    def set_representation_info(self, representation, info):
        self.representations[representation.unique_id()] = info

    @classmethod
    def main(cls):
        parser = argparse.ArgumentParser(
            description='DASH live manifest validator')
        parser.add_argument('--strict', action='store_true', dest='strict',
                            help='Abort if an error is detected')
        parser.add_argument('-e', '--encrypted', action='store_true', dest='encrypted',
                            help='Stream is encrypted')
        parser.add_argument('-s', '--save',
                            help='save all fragments into <dest>',
                            action='store_true')
        parser.add_argument('-d', '--dest',
                            help='directory to store results',
                            required=False)
        parser.add_argument('-p', '--prefix',
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
        args = parser.parse_args(namespace=ValidatorOptions(strict=False))
        # FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s\n  [%(url)s]"
        FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
        logging.basicConfig(format=FORMAT)
        args.log = logging.getLogger(__name__)
        args.log.addFilter(HideMixinsFilter())
        if args.verbose > 0:
            args.log.setLevel(logging.DEBUG)
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
                logging.error(err)
                traceback.print_exc()
                if args.dest:
                    bdv.save_manifest()
                    filename = bdv.output_filename('error.txt', makedirs=True)
                    with open(filename, 'w') as err_file:
                        err_file.write(str(err) + '\n')
                        traceback.print_exc(file=err_file)
                if args.strict:
                    raise


if __name__ == "__main__":
    BasicDashValidator.main()
