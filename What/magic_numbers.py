import binascii
import yaml


class FileSignatures:
    def __init__(self):
        with open("Data/file_signatures.yaml", "r") as myfile:
            data = myfile.read()
            self.file_sigs = yaml.load(data, Loader=yaml.FullLoader)

    def open_file_loc(self, file_loc):
        with open(file_loc, "r") as myfile:
            r = myfile.read()
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
