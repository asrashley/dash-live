import io, os, struct, sys

#
# The following code is from http://www.bok.net/trac/bento4/browser/trunk/Source/Python/utils/mp4-dash.py
#    
class Mp4Atom:
    def __init__(self, type, size, position):
        self.type     = type
        self.size     = size
        self.position = position
        
    def __repr__(self):
        return 'Mp4Atom(%s,%d,%d)'%(self.type,self.size,self.position)    
        
def WalkAtoms(filename):
    cursor = 0
    atoms = []
    src = io.FileIO(filename, "rb")
    while True:
        try:
            size = src.read(4)
            if not size:
                break
            size = struct.unpack('>I', size)[0]
            type = src.read(4)
            if not type:
                break
            #print type,size
            if size == 1:
                size = struct.unpack('>Q', src.read(8))[0]
                #print 'size==1',type,size
            atoms.append(Mp4Atom(type, size, cursor))
            cursor += size
            src.seek(cursor)
        except:
            break
    src.close()
    return atoms    


atoms = WalkAtoms(sys.argv[1])
fragments=None
for atom in atoms:
    if atom.type=='ftyp':
        #print 'Init seg',atom
        fragments = [(atom.position, atom.size)]
    elif atom.type=='moof':
        #print 'Fragment %d '%len(fragments),atom
        fragments.append( (atom.position, atom.size) )
    elif atom.type in ['sidx','moov','mdat','free'] and fragments:
        fragments[-1] = (fragments[-1][0],atom.position - fragments[-1][0] + atom.size) 
        #print('Extend fragment %d with %s to %d'%(len(fragments)-1, atom.type, fragments[-1][1]))
        
#print fragments
filename = os.path.splitext(sys.argv[1])[0]
print('Creating '+filename+'.py')
dest = open(filename+'.py', 'wb')
dest.write('filename="')
dest.write(sys.argv[1].replace('\\','/'))
dest.write('"\r\n')
dest.write('fragments=')
dest.write(str(fragments))
dest.write('\r\n')
dest.close()

