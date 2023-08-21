from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass(slots=True, frozen=True)
class TimeValues:
    mode: str
    elapsedTime: datetime
    timeShiftBufferDepth: timedelta
    mediaDuration: timedelta
