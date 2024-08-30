#############################################################################
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

import logging
from typing import Optional

from lxml import etree as ET

from dashlive.server import models
from dashlive.mpeg.dash.validator import (
    DashValidator, HttpClient, ValidationFlag, ValidatorOptions, WorkerPool
)

from .mixin import HideMixinsFilter

class ViewsTestDashValidator(DashValidator):
    def __init__(self,
                 http_client: HttpClient,
                 mode: str,
                 url: str,
                 duration: int,
                 pool: WorkerPool,
                 encrypted: bool = False,
                 check_media: bool = True,
                 debug: bool = False) -> None:
        opts = ValidatorOptions(duration=duration, encrypted=encrypted, pool=pool)
        if not check_media:
            opts.verify &= ~ValidationFlag.MEDIA
        opts.log = logging.getLogger(__name__)
        opts.log.addFilter(HideMixinsFilter())
        if debug:
            opts.log.setLevel(logging.DEBUG)
        super().__init__(
            url=url,
            http_client=http_client,
            mode=mode,
            options=opts)

    async def load(self,
                   xml: Optional[ET.ElementBase] = None,
                   data: Optional[bytes] = None) -> bool:
        rv = await super().load(xml=xml, data=data)
        for mf in models.MediaFile.all():
            self.set_representation_info(mf.representation)
        return rv
