import binascii
import json
import os


class FileSignatures:
    def __init__(self):
        path = "Data/file_signatures.json"
        fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        with open(fullpath, "r", encoding="utf8", errors="ignore") as myfile:
            self.file_sigs = json.load(myfile)

    def open_file_loc(self, file_loc):
        with open(file_loc, "r", encoding="utf8", errors="ignore") as myfile:
            r = myfile.readlines()
        return r

    def open_binary_scan_magic_nums(self, file_loc):
        with open(file_loc, "rb") as myfile:
            header = myfile.read(24)
            header = str(binascii.hexlify(header))[2:-1]
        return self.check_magic_nums(header)

    def check_magic_nums(self, text):
        for i in self.file_sigs:
            to_check = i["Hexadecimal File Signature"]
            # Say we have "16 23 21", the [0, len()] prevents it from executing
            # as magic numbers only count at the start of the file.
            if to_check == text[0 : len(to_check)]:
                # A file can only be one type
                return i
        return None
