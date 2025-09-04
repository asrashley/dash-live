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
class EncodedRepresentation:
    source: Path
    content_type: str
    file_index: int
    rep_id: str
    dest_track_id: int
    src_track_id: int | None = None
    role: str | None = None
    duration: float | None = None
    segment_duration: float | None = None

    def mp4box_track_id(self) -> str | None:
        tk_id: str | None = None
        if self.src_track_id is not None:
            return f"trackID={self.src_track_id}"
        if self.content_type == 'v':
            return "video"

        if self.content_type == 'a':
            tk_id = "audio"
        elif self.content_type == 't':
            tk_id = "text"
        if tk_id is not None:
            tk_id += f"{self.file_index}"
        return tk_id

    def mp4box_name(self) -> str:
        name: str = f"{self.source.absolute()}"
        tk_id: str | None = self.mp4box_track_id()
        if tk_id is not None:
            name += f"#{tk_id}"
        if self.role is not None:
            name += f":role={self.role}"
        name += f":id={self.rep_id}"
        if self.duration is not None:
            name += f":dur={self.duration}"
        if self.segment_duration is not None:
            name += f":ddur={self.segment_duration}"
        return name
