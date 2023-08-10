from typing import Literal, TypeAlias

supported_modes = {'live', 'vod', 'odvod'}

ModeType: TypeAlias = Literal['live', 'vod', 'odvod']

primary_profiles = {
    'odvod': 'urn:mpeg:dash:profile:isoff-on-demand:2011',
    'live': 'urn:mpeg:dash:profile:isoff-live:2011',
    'vod': 'urn:mpeg:dash:profile:isoff-live:2011',
}

additional_profiles = {
    'dvb': 'urn:dvb:dash:profile:dvbdash:2014',
}
