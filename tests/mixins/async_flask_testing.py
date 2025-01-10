"""
A version of flask_testing TestCase that supports async functions.
Copied from flask_testing.utils
"""

from abc import abstractmethod
import asyncio
import json
from typing import Callable, ClassVar, TypeVar
from unittest import IsolatedAsyncioTestCase

from flask import Flask
from flask.testing import FlaskClient
from werkzeug import Response
from werkzeug.utils import cached_property

T = TypeVar('T')

async def call(f: Callable[[], T]) -> T:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor=None, func=f)


class AsyncTestClient(FlaskClient):
    """
    A facade for the flask test client that provides an
    async response.
    """

    async def get(self, *args, **kwargs) -> Response:
        parent = super()
        return await call(lambda: parent.get(*args, **kwargs))

    async def post(self, *args, **kwargs) -> Response:
        parent = super()
        return await call(lambda: parent.post(*args, **kwargs))

    async def delete(self, *args, **kwargs) -> Response:
        parent = super()
        return await call(lambda: parent.delete(*args, **kwargs))

    async def put(self, *args, **kwargs) -> Response:
        parent = super()
        return await call(lambda: parent.put(*args, **kwargs))


class JsonResponseMixin(object):
    """
    Mixin with testing helper methods
    """

    @cached_property
    def json(self):
        return json.loads(self.data)


def _make_test_response(response_class):
    class TestResponse(response_class, JsonResponseMixin):
        pass

    return TestResponse

class AsyncFlaskTestCase(IsolatedAsyncioTestCase):
    render_templates: ClassVar[bool] = True
    app: Flask

    @abstractmethod
    def create_app(self):
        """
        Create your Flask app here, with any
        configuration you need.
        """
        raise NotImplementedError

    async def asyncSetUp(self) -> None:
        await self._pre_setup()
        self.addAsyncCleanup(self._post_teardown)

    async def _pre_setup(self) -> None:
        self.app = self.create_app()

        self._orig_response_class = self.app.response_class
        self.app.response_class = _make_test_response(self.app.response_class)

        self.client = self.app.test_client()
        self.async_client = AsyncTestClient(self.app, Response, True)

        self._ctx = self.app.test_request_context()
        self._ctx.push()

    async def _post_teardown(self) -> None:
        if getattr(self, '_ctx', None) is not None:
            self._ctx.pop()
            del self._ctx

        if getattr(self, 'app', None) is not None:
            if getattr(self, '_orig_response_class', None) is not None:
                self.app.response_class = self._orig_response_class
            del self.app

        if hasattr(self, 'async_client'):
            del self.async_client

        if hasattr(self, 'client'):
            del self.client

    def assert200(self, response) -> None:
        self.assertEqual(response.status_code, 200)

    def assert400(self, response) -> None:
        self.assertEqual(response.status_code, 400)

    def assert401(self, response) -> None:
        self.assertEqual(response.status_code, 401)

    def assert404(self, response) -> None:
        self.assertEqual(response.status_code, 404)
