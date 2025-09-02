from typing import Literal, TypeAlias

supported_modes: set[str] = {'live', 'vod', 'odvod'}

ModeType: TypeAlias = Literal['live', 'vod', 'odvod']

primary_profiles: dict[str, str] = {
    'odvod': 'urn:mpeg:dash:profile:isoff-on-demand:2011',
    'live': 'urn:mpeg:dash:profile:isoff-live:2011',
    'vod': 'urn:mpeg:dash:profile:isoff-live:2011',
}

additional_profiles: dict[str, str] = {
    'dvb': 'urn:dvb:dash:profile:dvb-dash:2014',
}
