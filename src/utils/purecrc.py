# See https://gist.github.com/Lauszus/6c787a3bc26fea6e842dfb8296ebd630

class Crc32Mpeg2(object):
    MPEG2_CRC32_POLY = 0x04C11DB7

    def __init__(self, size=32, poly=MPEG2_CRC32_POLY, crc=0xFFFFFFFF, ref_in=False, ref_out=False, xor_out=0):
        self.size = size
        self.generator = 1 << size | poly  # Generator polynomial
        self.ref_out = ref_out
        self.ref_in = ref_in
        self.crc = crc
        self.xor_out = xor_out

    def process(self, data):
        # Loop over the data
        for d in data:
            # Reverse the input byte if the flag is true
            if self.ref_in:
                d = self.reflect_data(d, 8)

            # XOR the top byte in the CRC with the input byte
            self.crc ^= d << (self.size - 8)

            # Loop over all the bits in the byte
            for _ in range(8):
                # Start by shifting the CRC, so we can check for the top bit
                self.crc <<= 1

                # XOR the CRC if the top bit is 1
                if self.crc & (1 << self.size):
                    self.crc ^= self.generator

    def final(self):
        """
        Return CRC output
        """
        # Reverse the output if the flag is true
        if self.ref_out:
            self.crc = self.reflect_data(self.crc, self.size)

        # Return the CRC value
        return self.crc ^ self.xor_out

    @staticmethod
    def reflect_data(x, width):
        # See: https://stackoverflow.com/a/20918545
        if width == 8:
            x = ((x & 0x55) << 1) | ((x & 0xAA) >> 1)
            x = ((x & 0x33) << 2) | ((x & 0xCC) >> 2)
            x = ((x & 0x0F) << 4) | ((x & 0xF0) >> 4)
        elif width == 16:
            x = ((x & 0x5555) << 1) | ((x & 0xAAAA) >> 1)
            x = ((x & 0x3333) << 2) | ((x & 0xCCCC) >> 2)
            x = ((x & 0x0F0F) << 4) | ((x & 0xF0F0) >> 4)
            x = ((x & 0x00FF) << 8) | ((x & 0xFF00) >> 8)
        elif width == 32:
            x = ((x & 0x55555555) << 1) | ((x & 0xAAAAAAAA) >> 1)
            x = ((x & 0x33333333) << 2) | ((x & 0xCCCCCCCC) >> 2)
            x = ((x & 0x0F0F0F0F) << 4) | ((x & 0xF0F0F0F0) >> 4)
            x = ((x & 0x00FF00FF) << 8) | ((x & 0xFF00FF00) >> 8)
            x = ((x & 0x0000FFFF) << 16) | ((x & 0xFFFF0000) >> 16)
        else:
            raise ValueError('Unsupported width')
        return x
