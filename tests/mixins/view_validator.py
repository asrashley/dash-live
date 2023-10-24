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

from dashlive.server import models
from dashlive.mpeg.dash.validator import (
    DashValidator, HttpClient, ValidatorOptions, WorkerPool
)

from .mixin import HideMixinsFilter

class ViewsTestDashValidator(DashValidator):
    def __init__(self,
                 http_client: HttpClient,
                 mode: str,
                 url: str,
                 media_duration: int,
                 pool: WorkerPool,
                 encrypted: bool = False,
                 debug: bool = False) -> None:
        opts = ValidatorOptions(encrypted=encrypted, pool=pool)
        if mode == 'live':
            opts.duration = media_duration * 2
        else:
            opts.duration = media_duration // 2
        opts.log = logging.getLogger(__name__)
        opts.log.addFilter(HideMixinsFilter())
        if debug:
            opts.log.setLevel(logging.DEBUG)
        super().__init__(
            url=url,
            http_client=http_client,
            mode=mode,
            options=opts)
        self.log.debug('Check manifest: %s', url)

    async def load(self, xml=None) -> bool:
        rv = await super().load(xml)
        for mf in models.MediaFile.all():
            self.set_representation_info(mf.representation)
        return rv
