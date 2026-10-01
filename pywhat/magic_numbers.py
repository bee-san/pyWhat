import binascii

from pywhat.helper import read_json


def get_magic_nums(file_loc):
    with open(file_loc, "rb") as myfile:
        header = myfile.read(24)
        header = str(binascii.hexlify(header))[2:-1]
    return check_magic_nums(header)


def check_magic_nums(text):
    text = text.lower()
    # A file can only be one type. The longest signature is the most specific
    # one, e.g. the UTF-32LE byte order mark FFFE0000 starts with the UTF-16LE
    # one, FFFE.
    return max(
        (
            i
            for i in read_json("file_signatures.json")
            if text.startswith(i["Hexadecimal File Signature"].lower())
        ),
        key=lambda i: len(i["Hexadecimal File Signature"]),
        default=None,
    )
