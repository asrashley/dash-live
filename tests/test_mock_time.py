import asyncio
import datetime
import logging
import time
import unittest

from dashlive.utils.date_time import to_iso_datetime

# from .mixins.mixin import TestCaseMixin
from .mixins.mock_time import MockTime, async_mock_time

class TestMockTime(unittest.IsolatedAsyncioTestCase):
    def test_unix_epoch(self) -> None:
        epoch = '1970-01-01T00:00:00Z'
        with MockTime(epoch):
            self.assertEqual(to_iso_datetime(datetime.datetime.now()), epoch)
            self.assertEqual(to_iso_datetime(datetime.datetime.utcnow()), epoch)
            self.assertAlmostEqual(time.time(), 0)
            expected: time.struct_time = (1970, 1, 1, 0, 0, 0, 3, 1, 0)
            self.assertEqual(time.localtime(), expected)

    def test_time_sleep(self) -> None:
        now = '2024-02-09T10:52:00Z'
        with MockTime(now):
            before = datetime.datetime.now()
            time.sleep(30)
            after = datetime.datetime.now()
            self.assertEqual(after - before, datetime.timedelta(seconds=30))
            self.assertEqual(
                to_iso_datetime(datetime.datetime.now()),
                '2024-02-09T10:52:30Z')

    async def test_asyncio_sleep(self) -> None:
        now = '2024-02-09T10:52:00Z'
        async with MockTime(now):
            before = datetime.datetime.now()
            await asyncio.sleep(25)
            after = datetime.datetime.now()
            self.assertEqual(after - before, datetime.timedelta(seconds=25))
            self.assertEqual(
                to_iso_datetime(datetime.datetime.now()),
                '2024-02-09T10:52:25Z')

    @async_mock_time('2024-02-09T10:52:00Z')
    async def test_async_mock_time_decorator(self) -> None:
        before = datetime.datetime.now()
        self.assertEqual(to_iso_datetime(before), '2024-02-09T10:52:00Z')
        await asyncio.sleep(25)
        after = datetime.datetime.now()
        self.assertEqual(after - before, datetime.timedelta(seconds=25))
        self.assertEqual(
            to_iso_datetime(datetime.datetime.now()),
            '2024-02-09T10:52:25Z')


if __name__ == "__main__":
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)
    unittest.main()
