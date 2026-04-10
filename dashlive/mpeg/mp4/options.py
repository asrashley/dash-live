import logging
from dataclasses import dataclass, field


@dataclass(slots=True, kw_only=True)
class Options:
    mode: str = 'r'
    lazy_load: bool = True
    debug: bool = False
    iv_size: int | None = None
    strict: bool = False
    bug_compatibility: str | set | None = None
    log: logging.Logger = field(init=False)

    def __post_init__(self):
        self.log = logging.getLogger('mp4')

    def has_bug(self, name):
        if self.bug_compatibility is None:
            return False
        if isinstance(self.bug_compatibility, str):
            self.bug_compatibility = {
                s.strip() for s in self.bug_compatibility.split(',')}
        return name in self.bug_compatibility
