import binascii

from pywhat.helper import read_json


def get_magic_nums(file_loc):
    with open(file_loc, "rb") as myfile:
        header = myfile.read(24)
        header = str(binascii.hexlify(header))[2:-1]
    return check_magic_nums(header)


def check_magic_nums(text):
    for i in read_json("file_signatures.json"):
        to_check = i["Hexadecimal File Signature"]
        if text.lower().startswith(to_check.lower()):
            # A file can only be one type
            return i
    return None
