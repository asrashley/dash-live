#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

from dashlive.utils.date_time import from_isodatetime

from .dash_option import DashOption, IntOrNoneDashOption
from .types import OptionUsage

class HttpErrorOption(DashOption[list[tuple[int, str]]]):
    def __init__(self, use: str, description: str) -> None:
        prefix: str = use[0]
        super().__init__(
            usage=OptionUsage.from_string(use),
            short_name=f'{prefix}he',
            full_name=f'{use}Errors',
            title=f'{description} HTTP errors',
            description=f'Cause an HTTP error to be generated when requesting {description}',
            cgi_name=f'{prefix}err',
            cgi_type='<code>=<num|isoDateTime>,..'
        )

    def from_string(self, value: str) -> list[tuple[int, str]]:
        if value.lower() in ['', 'none']:
            return []
        items: list[tuple] = []
        for val in value.split(','):
            code, pos = val.split('=')
            try:
                pos = int(pos, 10)
            except ValueError:
                pos = from_isodatetime(pos)
            items.append((int(code, 10), pos))
        return items

    def to_string(self, value: list[tuple[int, str]]) -> str:
        return str(value)


ManifestHttpError = HttpErrorOption('manifest', 'Manifest')

VideoHttpError = HttpErrorOption('video', 'Video fragments')

AudioHttpError = HttpErrorOption('audio', 'Audio fragments')

TextHttpError = HttpErrorOption('text', 'Text fragments')

FailureCount = IntOrNoneDashOption(
    usage=(OptionUsage.MANIFEST | OptionUsage.AUDIO | OptionUsage.VIDEO | OptionUsage.TEXT),
    short_name='hfc',
    full_name='failureCount',
    title='HTTP failure count',
    description=(
        'Number of times to respond with a 5xx error before ' +
        'accepting the request. Only relevant in combination ' +
        'with one of the error injection parameters (e.g. v503, m503).'),
    cgi_name='failures',
    cgi_type='<number>')
