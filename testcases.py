manifests = {
             'manifest_vod.mpd': { 'title':'Hand-made on demand profile',
                                  'details':['AAC and E-AC3 audio'],
                                  'mode':'vod',
                                  'static':True
                                  },
             'manifest_vod_aiv.mpd': { 'title':'AIV on demand profile',
                                  'details':['AAC and E-AC3 audio'],
                                  'mode':'vod',
                                  'static':True
                                  },
             'manifest_a.mpd': { 'title':'Vendor A live profile',
                                'details':['AAC audio'],
                                },
             'vod_manifest_b.mpd': { 'title':'Vendor B live profile',
                                    'details':['type="static"','AAC audio'],
                                    'static':True
                                    },
             'manifest_e.mpd': { 'title':'Vendor E live profile',
                                },
             'manifest_h.mpd':  { 'title':'Vendor H live profile',
                                'details':['utc:ntp UTCTiming element'],
                                },
             'manifest_i.mpd':  { 'title':'Vendor I live profile',
                                'details':['utc:direct UTCTiming element'],
                                },
             'enc.mpd': { 'title':'CENC VOD profile',
                         'static':True,
                         'mode':'vod',
                         'encrypted':True
                         },
}

page1_test_cases = [
              {
               'id':'vod_aac_1',
               'manifest': 'manifest_vod.mpd',
               'params':{ 'repr':'V3', 'acodec':'mp4a' },
               'details':['AAC audio'],
               },
              {
               'id':'vod_aac_2',
               'manifest': 'manifest_vod.mpd',
               'details':['AAC audio'],
               'params':{ 'repr':'V3', 'acodec':'mp4a', 'base':0 },
               },
              {
               'id':'vod_aac_3',
               'manifest': 'manifest_vod.mpd',
               'details':['AAC audio'],
               'params':{'acodec':'mp4a'}
               },
              {
               'id':'vod_eac_1',
               'manifest': 'manifest_vod.mpd',
               'params':{'repr':'V3', 'acodec':'ec-3'},
               'details':['E-AC3 audio'],
               },
              {
               'id':'vod_eac_2',
               'manifest': 'manifest_vod.mpd',
               'params':{'repr':'V3', 'acodec':'ec-3', 'base':0},
               'details':['E-AC3 audio'],
               },
              {
               'id':'vod_eac_3',
               'manifest': 'manifest_vod.mpd',
               'params':{'acodec':'ec-3'},
               'details':['E-AC3 audio'],
               },
              {
               'id':'vod_aac_eac_1',
               'manifest': 'manifest_vod.mpd',
               'params':{'repr':'V3'}
               },
              {
               'id':'vod_aac_eac_2',
               'manifest': 'manifest_vod.mpd',
               'params':{}
               },

]

page2_test_cases = [
                    {
                     'id':'live_a_1',
                     'manifest':'manifest_a.mpd',
                     'params':{ 'repr':'V3' },
                     },
                    {
                     'id':'live_a_2',
                     'manifest':'manifest_a.mpd',
                     'params':{ },
                     },
                    {
                     'id':'live_b_1',
                     'manifest':'vod_manifest_b.mpd',
                     'params':{ 'repr':'V3' },
                     },
                    {
                     'id':'live_b_2',
                     'manifest':'vod_manifest_b.mpd',
                     'params':{ },
                     },
                    {
                     'id':'live_aac_e_1',
                     'manifest':'manifest_e.mpd',
                     'params':{ 'acodec':'mp4a', 'repr':'V3', 'mup':-1 },
                     'details':['AAC audio'],
                     },
                    {
                     'id':'live_aac_e_2',
                     'manifest':'manifest_e.mpd',
                     'params':{ 'acodec':'mp4a', 'repr':'V3' },
                     'details':['AAC audio'],
                     },
                    {
                     'id':'live_aac_e_3',
                     'manifest':'manifest_e.mpd',
                     'params':{ 'acodec':'mp4a' },
                     'details':['AAC audio'],
                     },
                    ]

page3_test_cases = [
                    {
                     'id':'live_eac3_e_1',
                     'manifest':'manifest_e.mpd',
                     'params':{ 'acodec':'ec-3', 'repr':'V3', 'mup':-1 },
                     'details':['E-AC3 audio'],
                     },
                    {
                     'id':'live_eac3_e_2',
                     'manifest':'manifest_e.mpd',
                     'params':{ 'acodec':'ec-3', 'repr':'V3' },
                     'details':['E-AC3 audio'],
                     },
                    {
                     'id':'live_eac3_e_3',
                     'manifest':'manifest_e.mpd',
                     'params':{ 'acodec':'ec-3' },
                     'details':['E-AC3 audio'],
                     },
                    {
                     'id':'live_h_1',
                     'manifest':'manifest_h.mpd',
                     'params': { 'repr':'V3', 'mup':-1 },
                     },
                    {
                     'id':'live_h_2',
                     'manifest':'manifest_h.mpd',
                     'params': { 'repr':'V3' },
                     },
                    {
                     'id':'live_h_3',
                     'manifest':'manifest_h.mpd',
                     'params': { },
                     },
                    {
                     'id':'live_i_1',
                     'manifest':'manifest_i.mpd',
                     'params': { 'repr':'V3' },
                     },
                    {
                     'id':'live_i_2',
                     'manifest':'manifest_i.mpd',
                     'params': { },
                     },
                    ]

page4_test_cases = [
                    {
                     'id':'vod_enc_1',
                     'manifest':'enc.mpd',
                     'params': { 'repr':'V3ENC' },
                     },
                    {
                     'id':'vod_enc_2',
                     'manifest':'enc.mpd',
                     'params': { },
                     },
                    {
                     'id':'live_enc_1',
                     'manifest':'enc.mpd',
                     'params': { 'repr':'V3ENC', 'mode':'live' },
                     'static':False,
                     'title':'CENC live profile'
                     },
                    {
                     'id':'live_enc_2',
                     'manifest':'enc.mpd',
                     'params': { 'mode':'live' },
                     'static':False,
                     'title':'CENC live profile'
                     },
                    {
                     'id':'vod_corrupt_1',
                     'manifest': 'manifest_vod.mpd',
                     'params':{ 'repr':'V3', 'acodec':'mp4a' },
                     'corruption':True,
                     'details':['AAC audio', 'Video corruption'],
                     },
                    {
                     'id':'vod_corrupt_2',
                     'manifest': 'manifest_vod.mpd',
                     'params':{ 'acodec':'mp4a' },
                     'corruption':True,
                     'details':['AAC audio', 'Video corruption'],
                     },
                    {
                     'id':'live_corrupt_1',
                     'manifest': 'manifest_e.mpd',
                     'params':{ 'repr':'V3', 'acodec':'mp4a' },
                     'corruption':True,
                     'details':['AAC audio', 'Video corruption'],
                     },
                    {
                     'id':'live_corrupt_2',
                     'manifest': 'manifest_e.mpd',
                     'params':{ 'acodec':'mp4a' },
                     'corruption':True,
                     'details':['AAC audio', 'Video corruption'],
                     },
                    ]

page5_test_cases = [
                    {
                     'id':'vod_404_1',
                     'manifest': 'manifest_vod.mpd',
                     'params':{ 'repr':'V3', 'acodec':'mp4a' },
                     'v404':True,
                     'details':['AAC audio', '404 errors'],
                     },
                    {
                     'id':'vod_404_2',
                     'manifest': 'manifest_vod.mpd',
                     'params':{ 'acodec':'mp4a' },
                     'v404':True,
                     'details':['AAC audio', '404 errors'],
                     },
                    {
                     'id':'live_404_1',
                     'manifest': 'manifest_e.mpd',
                     'params':{ 'repr':'V3', 'acodec':'mp4a' },
                     'v404':True,
                     'details':['AAC audio', '404 errors'],
                     },
                    {
                     'id':'live_404_2',
                     'manifest': 'manifest_e.mpd',
                     'params':{ 'acodec':'mp4a' },
                     'v404':True,
                     'details':['AAC audio', '404 errors'],
                     },
                    {
                     'id':'vod_503_1',
                     'manifest': 'manifest_vod.mpd',
                     'params':{ 'repr':'V3', 'acodec':'mp4a' },
                     'v503':True,
                     'details':['AAC audio', '503 errors'],
                     },
                    {
                     'id':'vod_503_2',
                     'manifest': 'manifest_vod.mpd',
                     'params':{ 'acodec':'mp4a' },
                     'v503':True,
                     'details':['AAC audio', '503 errors'],
                     },
                    {
                     'id':'live_503_1',
                     'manifest': 'manifest_e.mpd',
                     'params':{ 'repr':'V3', 'acodec':'mp4a' },
                     'v503':True,
                     'details':['AAC audio', '503 errors'],
                     },
                    {
                     'id':'live_503_2',
                     'manifest': 'manifest_e.mpd',
                     'params':{ 'acodec':'mp4a' },
                     'v503':True,
                     'details':['AAC audio', '503 errors'],
                     },
                    ]
page6_test_cases = [
                    {
                     'id':'aiv_1',
                     'manifest': 'manifest_vod_aiv.mpd',
                     'params':{ 'repr':'V3', 'acodec':'mp4a' },
                     'details':['AAC audio'],
                     },
                    {
                     'id':'aiv_2',
                     'manifest': 'manifest_vod_aiv.mpd',
                     'params':{ 'acodec':'mp4a' },
                     'details':['AAC audio'],
                     },
                    {
                     'id':'aiv_3',
                     'manifest': 'manifest_vod_aiv.mpd',
                     'params':{ 'repr':'V3' },
                     'details':['E-AC3 and AAC audio'],
                     },
                    {
                     'id':'aiv_4',
                     'manifest': 'manifest_vod_aiv.mpd',
                     'params':{ },
                     'details':['E-AC3 and AAC audio'],
                     }
]
test_cases = [ page1_test_cases, page2_test_cases, page3_test_cases, page4_test_cases, page5_test_cases, page6_test_cases ]

testcase_map = {}
for page in test_cases:
    for tst in page:
        testcase_map[tst['id']]=tst
