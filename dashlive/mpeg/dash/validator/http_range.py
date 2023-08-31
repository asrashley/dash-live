class HttpRange:
    def __init__(self, start: str, end: str | None = None) -> None:
        if end is None:
            start, end = start.split('-')
        self.start = int(start)
        self.end = int(end)

    def __str__(self) -> str:
        return f'{self.start}-{self.end}'
