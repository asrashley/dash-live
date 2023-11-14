from functools import wraps

from pyinstrument import Profiler

def profile_test(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        with Profiler(interval=0.03) as profiler:
            func(*args, **kwargs)
        profiler.print()
    return decorated_function

def profile_async_test(func):
    @wraps(func)
    async def decorated_function(*args, **kwargs):
        with Profiler(interval=0.03) as profiler:
            await func(*args, **kwargs)
        profiler.print()
    return decorated_function
