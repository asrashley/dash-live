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

from builtins import object
import io
import time

class Buffer(object):
    def __init__(self, pos, data):
        self.pos = pos
        self.buf = data
        self.data = memoryview(self.buf)
        self.size = len(data)
        self.timestamp = time.time()

    @property
    def end(self):
        return self.pos + self.size


class BufferedReader(io.RawIOBase):
    def __init__(self, reader, buffersize=16384, data=None, offset=0,
                 size=None, max_buffers=30):
        super(BufferedReader, self).__init__()
        # print('BufferedReader', reader, buffersize, offset, size)
        self.reader = reader
        self.buffers = {}
        self.buffersize = buffersize
        self.pos = 0
        self.offset = offset
        self.size = size
        self.max_buffers = max_buffers
        self.num_buffers = 0
        if data is not None:
            self.size = len(data)
            self.buffersize = self.size
            self.buffers[0] = Buffer(self.pos, data)
            self.num_buffers = 1
            self.max_buffers = self.num_buffers + 1

    def readable(self):
        return not self.closed

    def seek(self, offset, whence=io.SEEK_SET):
        # print('seek', offset, whence)
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            if self.size is None:
                self.reader.seek(0, io.SEEK_END)
                self.size = self.reader.tell() - self.offset
            self.pos = self.size + offset
        self.pos = max(0, self.pos)
        if self.size is not None:
            self.pos = min(self.pos, self.size)
        return self.pos

    def tell(self):
        return self.pos

    def seekable(self):
        return not self.closed

    def peek(self, size):
        # print('peek', self.pos, size)
        assert size > 0
        if self.size is not None:
            size = min(size, self.size - self.pos)
            if size <= 0:
                return r''
        bucket = self.pos // self.buffersize
        end = (self.pos + size) // self.buffersize
        bucket *= self.buffersize
        end *= self.buffersize
        offset = self.pos - bucket
        buf = io.BytesIO()
        todo = size
        while todo:
            self.cache(bucket)
            sz = min(todo, self.buffersize - offset)
            buf.write(self.buffers[bucket].data[offset:].tobytes())
            bucket += self.buffersize
            offset = 0
            todo -= sz
        data = buf.getvalue()
        buf.close()
        return data

    def cache(self, bucket):
        # print('cache', bucket)
        if bucket in self.buffers:
            return
        if self.num_buffers == self.max_buffers:
            remove = None
            oldest = None
            for k, v in self.buffers.items():
                if remove is None or v.timestamp < oldest:
                    remove = k
                    oldest = v.timestamp
            if remove is not None:
                del self.buffers[remove]
                self.num_buffers -= 1
        if self.reader.tell() != (bucket + self.offset):
            self.reader.seek(bucket + self.offset, io.SEEK_SET)
        b = Buffer(bucket, self.reader.read(self.buffersize))
        if self.size is None and b.size < self.buffersize:
            self.size = bucket + b.size
        self.buffers[bucket] = b
        self.num_buffers += 1
        assert self.num_buffers <= self.max_buffers

    def read(self, n=-1):
        # print('read', self.pos, n)
        if n == -1:
            return self.readall()
        if self.size is not None:
            n = min(n, self.size - self.pos)
            if n <= 0:
                return r''
        b = self.peek(n)
        self.pos += n
        return b[:n]

    def readall(self):
        self.reader.seek(self.pos)
        rv = self.reader.read()
        self.pos += len(rv)
        return rv
