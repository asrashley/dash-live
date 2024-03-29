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
# from logging.config import dictConfig
import sys
import time

from .concurrent_pool import ConcurrentWorkerPool
from .http_client import HttpClient
from .options import ValidatorOptions
from .progress import ConsoleProgress, NullProgress
from .requests_http_client import RequestsHttpClient
from .validator import DashValidator

class BasicDashValidator(DashValidator):
    def __init__(self, url: str, http_client: HttpClient,
                 options: ValidatorOptions) -> None:
        super().__init__(url, http_client, options=options)
        self.representations = {}
        self.url = url

    async def run(self) -> bool:
        log = logging.getLogger('DashValidator')
        if self.xml is None:
            log.info('Loading manifest: %s', self.url)
            if not await self.load():
                log.error('Failed to load manifest')
                return False
        if not await self.prefetch_media_info():
            log.error('Prefetch of media info failed')
            return False
        if self.options.dest:
            self.save_manifest()
        if self.mode == 'live':
            max_loops = 100
        else:
            max_loops = 2
        while not self.finished() and not self.progress.aborted() and max_loops > 0:
            try:
                log.info('Starting stream validation...')
                await self.validate()
                if not self.finished():
                    max_loops -= 1
                    await self.sleep()
                    log.info('Refreshing manifest')
                    await self.refresh()
            except KeyboardInterrupt:
                self.progress.abort()

    @classmethod
    async def main(cls) -> int:
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
            default=0,
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
        log_config = {
            'version': 1,
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'default',
                    'stream': 'ext://sys.stdout',
                },
            },
            'formatters': {
                'default': {
                    'datefmt': r'%H:%M:%S,uuu',
                    'format': r'%(asctime)-15s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s',
                }
            },
            'loggers': {
                'DashValidator': {
                    'level': 'INFO',
                },
                'mp4': {
                    'level': 'WARN',
                },
                'fio': {
                    'level': 'WARN',
                },
            },
            'root': {
                'level': 'INFO',
            },
        }
        if args.verbose > 0:
            log_config['root']['level'] = 'DEBUG'
            log_config['loggers']['DashValidator']['level'] = 'DEBUG'
            if args.verbose > 1:
                log_config['loggers']['mp4']['level'] = 'DEBUG'
                log_config['loggers']['fio']['level'] = 'DEBUG'
        logging.basicConfig(
            datefmt=r'%H:%M:%S',
            format='%(asctime)-8s:%(levelname)s:%(filename)s@%(lineno)d: %(message)s')
        # dictConfig(log_config)
        if args.ivsize is not None and args.ivsize > 16:
            args.ivsize = args.ivsize // 8
        kwargs = {**vars(args)}
        del kwargs['manifest']
        try:
            del kwargs['threads']
        except KeyError:
            pass
        log = logging.getLogger('DashValidator')
        progress = ConsoleProgress()
        if args.verbose > 0:
            log.setLevel(logging.DEBUG)
            progress = NullProgress()
        options = ValidatorOptions(log=log, progress=progress, **kwargs)
        max_workers: int | None = args.threads
        if max_workers < 1:
            max_workers = None
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            options.pool = ConcurrentWorkerPool(pool)
            bdv = cls(args.manifest, http_client=RequestsHttpClient(options), options=options)
            await bdv.run()
        options.progress.finished(args.manifest)
        sys.stdout.write('\n')
        duration = time.time() - start_time
        if not bdv.has_errors():
            print(f'No errors found. Validation took {duration:#5.1f} seconds')
            return 0
        errors = bdv.get_errors()
        if args.dest:
            filename = bdv.output_filename(
                default='errors.txt', filename='errors.txt',
                makedirs=True, bandwidth=None)
            with open(filename, 'wt') as err_file:
                for err in errors:
                    err_file.write(f'{err}\n')
        else:
            for err in errors:
                print(err)
        print(f'Finished with {len(errors)} errors after {duration:#5.1f} seconds')
        return 1
