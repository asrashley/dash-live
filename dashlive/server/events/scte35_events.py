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

import flask

from dashlive.mpeg import MPEG_TIMEBASE
from dashlive.scte35 import descriptors
from dashlive.scte35.binarysignal import BinarySignal, SapType
from dashlive.scte35.splice_insert import SpliceInsert
from dashlive.utils.objects import merge

from .repeating_event_base import RepeatingEventBase

class Scte35Events(RepeatingEventBase):
    """
    Generates SCTE35 events that alternate between placement opportunity start
    and end.
    """
    schemeIdUri = "urn:scte:scte35:2014:xml+bin"
    DEFAULT_VALUES = merge(RepeatingEventBase.DEFAULT_VALUES, {
        "program_id": 1620,
        "value": "",  # DVB-DASH states that value should be absent
    })

    PREFIX = 'scte35'

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if self.inband:
            self.version = 1

    def get_manifest_event_payload(self, event_id: int, presentation_time: int) -> str:
        splice = self.create_binary_signal(event_id, presentation_time)
        data = splice.encode()
        xml = flask.render_template('events/scte35_xml_bin_event.xml', binary=data)
        return xml

    def get_emsg_event_payload(self, event_id: int, presentation_time: int) -> bytes:
        splice = self.create_binary_signal(event_id, presentation_time)
        return splice.encode()

    def create_binary_signal(self, event_id: int, presentation_time: int) -> BinarySignal:
        pts = presentation_time * MPEG_TIMEBASE // self.timescale
        duration = self.duration * MPEG_TIMEBASE // self.timescale
        # auto_return is True for the OUT and False for the IN
        auto_return = (event_id & 1) == 0
        if self.count > 0:
            avail_num = 1 + (event_id // 2)
            avails_expected = 1 + (self.count // 2)
        else:
            avails_expected = avail_num = 0

        # According to ETSI TS 103 752-1 V1.1.1 the Placement Opportunity
        # and Advertisement segmentation_descriptors may be of type
        # "Provider" or "Distributor"
        segmentation_descriptor = descriptors.SegmentationDescriptor(
            segmentation_event_id=avail_num,
            segmentation_duration=0,
            segmentation_type=(
                descriptors.SegmentationTypeId.PROVIDER_PLACEMENT_OP_START +
                (event_id & 1)))
        splice = BinarySignal(
            sap_type=SapType.CLOSED_GOP_NO_LEADING_PICTURES,
            splice_insert=SpliceInsert(
                out_of_network_indicator=True,
                splice_time={
                    "pts": pts
                },
                avails_expected=avails_expected,
                splice_event_id=event_id,
                program_splice_flag=True,
                avail_num=avail_num,
                unique_program_id=self.program_id,
                break_duration={
                    "duration": duration,
                    "auto_return": auto_return,
                }
            ),
            descriptors=[
                segmentation_descriptor,
            ],
        )
        return splice
