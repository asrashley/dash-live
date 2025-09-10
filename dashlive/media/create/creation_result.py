#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
from dataclasses import dataclass
from pathlib import Path

@dataclass
class CreationResult:
    filename: Path
    content_type: str
    track_id: int
    duration: float | None
