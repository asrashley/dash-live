options = [
    {
        'name': 'mode',
        'title': 'Operating mode',
        'options': [
            ('VOD live profile', 'mode=vod'),
            ('Live stream', 'mode=live'),
            ('VOD OD profile', 'mode=odvod'),
        ]
    },
    {
        'name': 'rep',
        'title': 'Adaptive bitrate',
        'options': [
            ('no', 'rep=V3'),
            ('yes', ''),
        ]
    },
    {
        'name': 'acodec',
        'title': 'Audio codec',
        'options': [
            ('AAC', 'acodec=mp4a'),
            ('E-AC3', 'acodec=ec-3'),
            ('Both AAC and E-AC3', ''),
        ]
    },
    {
        'name': 'drm',
        'title': 'Encryption',
        'options': [
            ('None', 'drm=none'),
            ('PlayReady', 'drm=playready'),
            ('Marlin', 'drm=marlin'),
            ('ClearKey', 'drm=clearkey'),
            ('All', 'drm=all'),
        ]
    },
    {
        'name': 'drmloc',
        'title': 'DRM location',
        'options': [
            ('All locations', ''),
            ('mspr:pro element in MPD', 'drmloc=pro'),
            ('dash:cenc element in MPD', 'drmloc=cenc'),
            ('PSSH in init segment', 'drmloc=moov'),
            ('mspr:pro + dash:cenc in MPD', 'drmloc=pro-cenc'),
            ('mspr:pro MPD + PSSH init', 'drmloc=pro-moov'),
            ('dash:cenc MPD + PSSH init', 'drmloc=cenc-moov'),
        ]
    },
    {
        'name': 'time',
        'title': 'UTC timing element',
        'options': [
            ('None', ''),
            ('xsd:date', 'time=xsd'),
            ('iso datetime', 'time=iso'),
            ('NTP', 'time=ntp'),
            ('HTTP HEAD', 'time=head'),
        ]
    },
    {
        'name': 'base',
        'title': 'BaseURL element',
        'options': [
            ('Yes', ''),
            ('No', 'base=0'),
        ]
    },
]
