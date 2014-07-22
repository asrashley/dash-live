#

import V1,V2,V3,A1
import os

class Representation(object):
    def __init__(self, id, codecs, filename, duration, bandwidth, segments, **kwargs):
        self.id = id
        self.codecs = codecs
        self.filename = filename
        self.bandwidth = bandwidth
        self.duration = duration
        self.segments = segments
        self.startWithSAP = kwargs['startWithSAP'] 
        try:
            self.lang = kwargs['lang']
        except KeyError:
            pass
        if codecs.startswith('avc'):
            self.width = kwargs['width']
            self.height = kwargs['height']
            self.frameRate = kwargs['frameRate']
            try:
                self.sar = kwargs['sar']
            except KeyError:
                pass
            self.scanType = kwargs['scanType']
        elif codecs.startswith('mp4a'):
            self.sampleRate = kwargs['sampleRate']
            self.numChannels = kwargs['numChannels'] 

        
representations = { 'V1':Representation( 
                          id='V1',
                          codecs="avc1.4D001E",
                          width=352,
                          height=288, 
                          duration=5120, 
                          startWithSAP=1, 
                          bandwidth=683133, 
                          frameRate=25, 
                          sar="22:17", 
                          scanType="progressive",
                          filename=V1.filename, 
                          segments=V1.fragments 
                          ),
                   'V2':Representation( 
                          id='V2',
                          codecs="avc1.4D001E",
                          width=1024,
                          height=576, 
                          duration=5120, 
                          startWithSAP=1, 
                          bandwidth=1005158, 
                          frameRate=25, 
                          sar="22:17", 
                          scanType="progressive", 
                          filename=V2.filename, 
                          segments=V2.fragments 
                          ),                   
                   'V3':Representation( 
                          id='V3',
                          codecs="avc1.4D001E",
                          width=1024,
                          height=576, 
                          duration=5120, 
                          startWithSAP=1, 
                          bandwidth=1289886, 
                          frameRate=25, 
                          sar="22:17", 
                          scanType="progressive", 
                          filename=V3.filename, 
                          segments=V3.fragments 
                          ),                   
                   'A1':Representation( 
                         id='A1', 
                         codecs="mp4a.40.02", 
                         sampleRate=48000, 
                         duration=3989, 
                         numChannels=2, 
                         lang='eng', 
                         startWithSAP=1, 
                         bandwidth=95170, 
                         filename=A1.filename, 
                         segments=A1.fragments
                         )
                   }
