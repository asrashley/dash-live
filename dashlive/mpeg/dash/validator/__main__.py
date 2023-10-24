#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################
import asyncio

from .basic import BasicDashValidator

if __name__ == "__main__":
    asyncio.run(BasicDashValidator.main())
