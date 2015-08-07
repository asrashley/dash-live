class Box(object):
    def __init__(self, pos, size):
        self.pos = pos
        self.size = size

class Segment(object):
    def __init__(self, **kwargs):
        self.boxes={}
        self.add(**kwargs)
    def add(self,**kwargs):
        for k,v in kwargs.iteritems():
            try:
                self.boxes[k]=Box(v.position,v.size)
            except AttributeError:
                self.boxes[k]=Box(v[0],v[1])
    def __getattr__(self, key):
        if key=='boxes':
            return object.__getattribute__(self, 'boxes')
        b = object.__getattribute__(self, 'boxes')
        try:
            return b[key]
        except KeyError:
            raise  AttributeError(key) 
    def __repr__(self):
        rv= []
        seg = self.boxes['seg']
        for k,v in self.boxes.iteritems():
            if k!='seg' and v.pos>seg.pos:
                rv.append('"%s":(%d,%d)'%(k,v.pos-seg.pos,v.size))
            else:
                rv.append('"%s":(%d,%d)'%(k,v.pos,v.size))
        rv = ','.join(rv)
        return '{'+rv+'}'

class Representation(object):
    FIELDS = ['bitrate', 'codecs', 'duration', 'encrypted', 'filename', 
              'frameRate', 'height', 'lang', 'numChannels', 'sampleRate',
              'sar', 'scanType', 'segments',
              'startWithSAP', 'timescale', 'width']
    def __init__(self, id,  **kwargs):
        def convert_dict(item):
            if isinstance(item,dict):
                item = Segment(**item)
            return item
        
        self.id = id
        self.segments=[]
        self.startWithSAP = 1
        self.encrypted=False
        self.codecs=''
        for key,value in kwargs.iteritems():
            object.__setattr__(self, key, value)
        self.segments = [convert_dict(s) for s in self.segments]
        if self.segments:
            self.num_segments = len(self.segments)-1
    def __repr__(self):
        args=[]
        for key,value in self.__dict__.iteritems():
            if key=='num_segments':
                continue
            if isinstance(value,str):
                value = '"%s"'%value
            else:
                value=str(value)
            args.append('%s=%s'%(key,value))
        args = ','.join(args)
        return 'Representation('+args+')'