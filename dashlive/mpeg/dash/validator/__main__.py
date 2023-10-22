#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import gevent.monkey
gevent.monkey.patch_all()

import asyncio

import asyncio_gevent

asyncio.set_event_loop_policy(asyncio_gevent.EventLoopPolicy())

from .basic import BasicDashValidator

if __name__ == "__main__":
    asyncio.run(BasicDashValidator.main())
