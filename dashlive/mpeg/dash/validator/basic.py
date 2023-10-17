#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import argparse
from concurrent.futures import ThreadPoolExecutor
import logging
import sys
import time

from .validator import DashValidator
from .options import ValidatorOptions
from .pool import WorkerPool
from .progress import ConsoleProgress
from .requests_http_client import RequestsHttpClient

class BasicDashValidator(DashValidator):
    def __init__(self, url: str, options: ValidatorOptions) -> None:
        super().__init__(
            url,
            RequestsHttpClient(options),
            options=options)
        self.representations = {}
        self.url = url

    @classmethod
    def main(cls) -> int:
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
        parser.add_argument('--title',
                            help='Title to use for stream when storing media files',
                            required=False)
        parser.add_argument('--duration',
                            help='Maximum duration (in seconds)',
                            type=int,
                            required=False)
        parser.add_argument(
            '--threads',
            dest='threads',
            help='Use mulit-threaded validation with a maximum number of threads (0=auto)',
            type=int,
            default=None,
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
        args = parser.parse_args()
        FORMAT = r"%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s"
        logging.basicConfig(format=FORMAT)
        log = logging.getLogger('DashValidator')
        if args.verbose > 0:
            log.setLevel(logging.DEBUG)
            if args.verbose > 1:
                logging.getLogger('mp4').setLevel(logging.DEBUG)
                logging.getLogger('fio').setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)
        if args.ivsize is not None and args.ivsize > 16:
            args.ivsize = args.ivsize // 8
        kwargs = {**vars(args)}
        del kwargs['manifest']
        try:
            del kwargs['threads']
        except KeyError:
            pass
        options = ValidatorOptions(log=log, progress=ConsoleProgress(), **kwargs)
        if args.threads is not None:
            max_workers: int | None = args.threads
            if max_workers < 1:
                max_workers = None
            options.pool = WorkerPool(ThreadPoolExecutor(max_workers=max_workers))
        start_time = time.time()
        bdv = cls(args.manifest, options=options)
        log.info('Loading manifest: %s', args.manifest)
        if not bdv.load():
            log.error('Failed to load manifest')
            return 1
        bdv.prefetch_media_info()
        if args.dest:
            bdv.save_manifest()
        while not bdv.finished() and not options.progress.aborted():
            try:
                log.info('Starting stream validation...')
                bdv.validate()
                if not bdv.finished():
                    bdv.sleep()
                    log.info('Refreshing manifest')
                    bdv.refresh()
            except KeyboardInterrupt:
                options.progress.abort()
        options.progress.finished(args.manifest)
        sys.stdout.write('\n')
        duration = time.time() - start_time
        if not bdv.has_errors():
            print(f'No errors found. Validation took {duration:#5.1f} seconds')
            return 0
        if args.dest:
            filename = bdv.output_filename(
                default='errors.txt', filename='errors.txt',
                makedirs=True, bandwidth=None)
            with open(filename, 'wt') as err_file:
                for err in bdv.get_errors():
                    err_file.write(f'{err}\n')
        else:
            for err in bdv.get_errors():
                print(err)
        print(f'Finished with errors after {duration:#5.1f} seconds')
        return 1