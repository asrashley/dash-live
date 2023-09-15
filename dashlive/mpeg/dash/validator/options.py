#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dataclasses import dataclass, field
from logging import Logger

from dashlive.utils.date_time import RelaxedDateTime, UTC

from .progress import Progress

@dataclass(slots=True, kw_only=True)
class ValidatorOptions:
    """
    Options that can be passed to the DASH validator
    """
    strict: bool = True
    encrypted: bool = False
    save: bool = False
    ivsize: int | None = None
    dest: str | None = None
    duration: int | None = None
    prefix: str | None = None
    verbose: bool = False
    start_time: RelaxedDateTime = field(default_factory=lambda: RelaxedDateTime.now(UTC()))
    progress: Progress | None = None
    log: Logger | None = None
    manifest: str = field(init=False)
