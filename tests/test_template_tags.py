import binascii
import datetime
import logging
import unittest

from dashlive.utils.date_time import UTC
import dashlive.server.template_tags as tags

class TestTemplateTags(unittest.TestCase):
    def test_dateTimeFormat(self) -> None:
        testcases = [
            (None, '', None),
            ("2023-07-18T20:10:02Z", "%H:%M:%S %d/%m/%Y", '20:10:02 18/07/2023'),
            ("Jul 18 2023 20:10", "%H:%M:%S %d/%m/%Y", '20:10:00 18/07/2023'),
            (
                datetime.datetime(2023, 7, 18, 20, 10, 2, tzinfo=UTC()),
                "%H:%M:%S %d/%m/%Y",
                '20:10:02 18/07/2023'
            ),
        ]
        for value, fmt, expected in testcases:
            actual = tags.dateTimeFormat(value, fmt)
            self.assertEqual(expected, actual)

    def test_sizeFormat(self) -> None:
        kilobyte = 1024
        megabyte = kilobyte * 1024
        gigabyte = megabyte * 1024
        kibibyte = 1000
        mibibyte = 1000 * kibibyte
        gibibyte = 1000 * mibibyte
        testcases = [
            (123, True, '123 B'),
            (123, False, '123 b'),
            (12 * kilobyte, True, '12 KB'),
            (23 * megabyte, True, '23 MB'),
            (34 * gigabyte, True, '34 GB'),
            (345 * gigabyte, True, '345 GB'),
            (3456 * gigabyte, True, '3 TB'),
            (12 * kibibyte, False, '12 Kb'),
            (23 * mibibyte, False, '23 Mb'),
            (34 * gibibyte, False, '34 Gb'),
            (345 * gibibyte, False, '345 Gb'),
            (3456 * gibibyte, False, '3 Tb'),
            (345 * gigabyte, False, '370 Gb'),
            (7899 * gibibyte, False, '7 Tb'),
            (7899 * gigabyte, False, '8 Tb'),
        ]
        for value, binary, expected in testcases:
            units = 'B' if binary else 'b'
            actual = tags.sizeFormat(value, binary, units)
            self.assertEqual(expected, actual)

    def test_toHtmlString(self) -> None:
        value = {
            'hello': 'world',
            'another': 'row',
            'boolean': True,
        }
        actual = tags.toHtmlString(value)
        expected = '''<table>
<tr><td>hello</td><td>world</td></tr>
<tr><td>another</td><td>row</td></tr>
<tr><td>boolean</td><td><span class="bool-yes">&check;</span></td></tr>
</table>'''
        self.assertIsInstance(actual, tags.HtmlSafeString)
        self.assertEqual(expected, actual.html)
        actual = tags.toHtmlString(value, 'my-class-name')
        expected = '''<table class="my-class-name">
<tr><td>hello</td><td>world</td></tr>
<tr><td>another</td><td>row</td></tr>
<tr><td>boolean</td><td><span class="bool-yes">&check;</span></td></tr>
</table>'''
        self.assertIsInstance(actual, tags.HtmlSafeString)
        self.assertEqual(expected, actual.html)

        actual = tags.toHtmlString(True)
        expected = r'<span class="bool-yes">&check;</span>'
        self.assertEqual(expected, actual.html)

        actual = tags.toHtmlString(False)
        expected = r'<span class="bool-no">&cross;</span>'
        self.assertEqual(expected, actual.html)

        actual = tags.toHtmlString([True, False])
        expected = r'[<span class="bool-yes">&check;</span>,<span class="bool-no">&cross;</span>]'
        self.assertEqual(expected, actual.html)

        actual = tags.toHtmlString((True, False))
        expected = r'(<span class="bool-yes">&check;</span>,<span class="bool-no">&cross;</span>)'
        self.assertEqual(expected, actual.html)

        actual = tags.toHtmlString('a string')
        expected = 'a string'
        self.assertEqual(expected, actual.html)

        actual = tags.toHtmlString('a string', 'class-name')
        expected = r'<span class="class-name">a string</span>'
        self.assertEqual(expected, actual.html)

    def test_toJson(self) -> None:
        actual = tags.toJson(None)
        self.assertEqual(None, actual)

        actual = tags.toJson(True)
        self.assertEqual("true", actual)

        actual = tags.toJson([True, False])
        self.assertEqual("[true, false]", actual)

        actual = tags.toJson([True, False], indent=2)
        self.assertEqual("[\n  true,\n  false\n]", actual)

        value = {
            'hello': 'world',
            'boolean': True,
            'number': 42,
        }
        actual = tags.toJson(value)
        expected = r'{"hello": "world", "boolean": true, "number": 42}'
        self.assertEqual(expected, actual)

    def test_toUuid(self) -> None:
        value = "9a04f07998404286ab92e65be0885f95"
        actual = tags.toUuid(value)
        expected = r'9A04F079-9840-4286-AB92-E65BE0885F95'
        self.assertEqual(expected, actual)

        value = binascii.a2b_hex(value)
        actual = tags.toUuid(value)
        self.assertEqual(expected, actual)

    def test_trueFalse(self) -> None:
        self.assertEqual("true", tags.trueFalse(True))
        self.assertEqual("true", tags.trueFalse(1))
        self.assertEqual("true", tags.trueFalse('true'))
        self.assertEqual("false", tags.trueFalse(False))
        self.assertEqual("false", tags.trueFalse(0))
        self.assertEqual("false", tags.trueFalse(''))
        self.assertEqual("false", tags.trueFalse(None))

    def test_sortedAttributes(self) -> None:
        value = {
            'foo': 0,
            'sort': 5,
            'any': 8,
            'zz': 'hello'
        }
        expected = ' any="8" foo="0" sort="5" zz="hello"'
        actual = tags.sortedAttributes(value)
        self.assertEqual(expected, actual)

        actual = tags.sortedAttributes({})
        self.assertEqual('', actual)

    def test_length(self) -> None:
        self.assertEqual(0, tags.length(None))
        self.assertEqual(0, tags.length(''))
        self.assertEqual(1, tags.length('1'))
        self.assertEqual(3, tags.length('abc'))

    def test_sort_icon(self) -> None:
        actual = tags.sort_icon('name', 'name', True)
        expected = r'<span class="float-right sort-arrow">&and;</span>'
        self.assertEqual(expected, actual.html)

        actual = tags.sort_icon('name', 'name', False)
        expected = r'<span class="float-right sort-arrow">&or;</span>'
        self.assertEqual(expected, actual.html)

        actual = tags.sort_icon('name', 'other', True)
        self.assertEqual('', actual)


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    unittest.main()
