#############################################################################
#
#  Project Name        :    Simulated MPEG DASH service
#
#  Author              :    Alex Ashley
#
#############################################################################

def print_line(start: int, hex_line: str, ascii_line: str) -> None:
    if len(hex_line) < 8:
        hex_line += ['   '] * (8 - len(hex_line))
    print('{:04d}: {}  {}'.format(
        start,
        ' '.join(hex_line),
        ' '.join(ascii_line)))

def hexdump_buffer(label: str, data: bytes, max_length: int = 256,
                   offset: int = 0, width: int = 16) -> None:
    print(f'==={label}===')
    hex_line = []
    ascii_line = []
    truncated = False
    max_length -= 1
    end = offset + max_length
    for idx, d in enumerate(data[offset:], start=offset):
        asc = chr(d) if d >= ord(' ') and d <= ord('z') else ' '
        hex_line.append(f'{d:02x} ')
        ascii_line.append(f'{asc} ')
        if len(hex_line) == width:
            print_line(1 + idx - width, hex_line, ascii_line)
            hex_line = []
            ascii_line = []
        if idx == end:
            truncated = True
            break
    if hex_line:
        print_line(idx - 7, hex_line, ascii_line)
    if truncated:
        print('.......')
    print('==={}==='.format('=' * len(label)))
