import asyncio
from contextlib import AsyncContextDecorator, ContextDecorator, asynccontextmanager
import datetime
import time
from typing import Any, Callable, ClassVar, ContextManager
from unittest import mock

from dashlive.utils.date_time import from_isodatetime

class MockTime(ContextDecorator, AsyncContextDecorator):
    real_datetime_class = datetime.datetime
    real_asyncio_sleep: ClassVar[Callable[[float], None]] = asyncio.sleep

    now: datetime.datetime

    def __init__(self, iso_now: str):
        self.now = from_isodatetime(iso_now)

        """
        Override ``datetime.datetime.now()`` with a custom target value.
        This creates a new datetime.datetime class, and alters its now()/utcnow()
        methods.
        Returns:
        A mock.patch context, can be used as a decorator or in a with.
        """
        # See http://bugs.python.org/msg68532
        # And
        # http://docs.python.org/reference/datamodel.html#customizing-instance-and-subclass-checks
        class DatetimeSubclassMeta(type):
            """
            We need to customize the __instancecheck__ method for isinstance().
            This must be performed at a metaclass level.
            """
            @classmethod
            def __instancecheck__(mcs, obj):
                return isinstance(obj, MockTime.real_datetime_class)

        class BaseMockedDatetime(MockTime.real_datetime_class):
            @classmethod
            def now(cls, tz=None) -> datetime.datetime:
                return cls._get_now().replace(tzinfo=tz)

            @classmethod
            def utcnow(cls) -> datetime.datetime:
                return cls._get_now()

            @classmethod
            def _get_now(cls) -> datetime.datetime:
                raise RuntimeError('_get_now should have been replaced')

        # Python2 & Python3-compatible metaclass
        MockedDatetime = DatetimeSubclassMeta(
            'datetime', (BaseMockedDatetime,), {})
        MockedDatetime._get_now = self.get_now
        self.datetime_patch = mock.patch.object(datetime, 'datetime', MockedDatetime)
        self.asyncio_patch = mock.patch.object(
            asyncio, 'sleep', self.mock_asyncio_sleep)
        self.time_patch = mock.patch.multiple(
            time,
            localtime=self.mock_time_localtime, sleep=self.mock_time_sleep,
            time=self.mock_time_time)

    def __enter__(self) -> ContextManager["MockTime"]:
        return self.__do_enter()

    async def __aenter__(self) -> ContextManager["MockTime"]:
        return self.__do_enter()

    def __do_enter(self) -> ContextManager["MockTime"]:
        self.asyncio_patch.start()
        self.datetime_patch.start()
        self.time_patch.start()
        return self

    def __exit__(self, *args) -> bool:
        self.__do_exit()
        return False

    async def __aexit__(self, *args) -> bool:
        self.__do_exit()
        return False

    def __do_exit(self) -> None:
        self.time_patch.stop()
        self.datetime_patch.stop()
        self.asyncio_patch.stop()

    def get_now(self) -> datetime.datetime:
        return self.now

    def mock_time_sleep(self, duration: float) -> None:
        self.now += datetime.timedelta(seconds=duration)

    async def mock_asyncio_sleep(self, duration: float, result: Any = None) -> None:
        self.now += datetime.timedelta(seconds=duration)
        return await MockTime.real_asyncio_sleep(0, result=result)

    def mock_time_time(self) -> float:
        return self.now.timestamp()

    def mock_time_localtime(self) -> time.struct_time:
        return self.now.timetuple()


@asynccontextmanager
async def async_mock_time(now: str) -> ContextManager[MockTime]:
    with MockTime(now) as mt:
        yield mt
