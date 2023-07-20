# See https://gist.github.com/Lauszus/6c787a3bc26fea6e842dfb8296ebd630

class Crc32Mpeg2(object):
    MPEG2_CRC32_POLY = 0x04C11DB7

    def __init__(self, size=32, poly=MPEG2_CRC32_POLY, crc=0xFFFFFFFF, xor_out=0):
        self.size = size
        self.generator = 1 << size | poly  # Generator polynomial
        self.crc = crc
        self.xor_out = xor_out

    def process(self, data):
        for d in data:
            self.crc ^= d << (self.size - 8)

            for _ in range(8):
                self.crc <<= 1
                if self.crc & (1 << self.size):
                    self.crc ^= self.generator

    def final(self):
        """
        Return CRC output
        """
        return self.crc ^ self.xor_out
