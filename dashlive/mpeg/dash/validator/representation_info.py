class RepresentationInfo:
    def __init__(self, encrypted, timescale, num_segments=0, **kwargs):
        self.encrypted = encrypted
        self.timescale = timescale
        self.num_segments = num_segments
        self.tested_media_segment = set()
        self.init_segment = None
        self.moov = None
        self.media_segments = []
        self.segments = []
        for k, v in kwargs.items():
            setattr(self, k, v)
