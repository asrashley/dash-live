import logging
import re
from unittest import TestCase, main

from dashlive.server.requesthandler.esm import UiComponents

class EsmTests(TestCase):
    def test_named_imports(self) -> None:
        text: list[str] = [
            r"import {html} from 'htm/preact';",
            r"import {navigate} from 'wouter-preact/use-browser-location';",
            r"import {Component} from 'preact';",
            r"import { html } from 'htm/preact';",
            r"import { useCallback } from 'preact/hooks';",
        ]
        start: logging.Pattern[str] = re.compile(r'^import\s+{\s*(?P<names>[^}]+)\s*}')
        mid: logging.Pattern[str] = re.compile(r'\s*}\s+from\s+')
        end: logging.Pattern[str] = re.compile(r'[\'"](?P<library>[^\'"]+)[\'"];?$')
        for line in text:
            match: re.Match | None = start.search(line)
            self.assertIsNotNone(match)
            match = mid.search(line)
            self.assertIsNotNone(match)
            match = end.search(line)
            self.assertIsNotNone(match)
            match = UiComponents.NAMED_IMPORT.search(line)
            self.assertIsNotNone(match)


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    main()
