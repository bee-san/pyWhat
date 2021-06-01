import os.path
import glob

from pywhat.magic_numbers import FileSignatures
from pywhat.nameThatHash import Nth
from pywhat.regex_identifier import RegexIdentifier


class Identifier:
    def __init__(self):
        self.regex_id = RegexIdentifier()
        self.file_sig = FileSignatures()
        self.name_that_hash = Nth()

    def identify(self, input: str, api=False) -> dict:
        identify_obj = {}
        identify_obj["File Signatures"] = {}
        identify_obj["Regexes"] = {}
        magic_numbers = []

        if os.path.isdir(input):
            # if input is a directory, recursively search for all of the files
            for myfile in glob.iglob(input + "**/**", recursive=True):
                if os.path.isfile(myfile):
                    magic_numbers = self.file_sig.open_binary_scan_magic_nums(myfile)
                    text = self.file_sig.open_file_loc(myfile)

                    if not magic_numbers:
                        magic_numbers = self.file_sig.check_magic_nums(myfile)

                    short_name = os.path.basename(myfile)
                    identify_obj["File Signatures"][short_name] = magic_numbers
                    identify_obj["Regexes"][short_name] = self.regex_id.check(text)


        elif os.path.isfile(input):
            short_name = os.path.basename(input)
            magic_numbers = self.file_sig.open_binary_scan_magic_nums(input)
            text = self.file_sig.open_file_loc(input)

            # if file doesn't exist, check to see if the inputted text is
            # a file in hex format
            if not magic_numbers:
                magic_numbers = self.file_sig.check_magic_nums(text)

            short_name = os.path.basename(input)
            identify_obj["File Signatures"][short_name] = magic_numbers
            identify_obj["Regexes"][short_name] = self.regex_id.check(text)

        else:
            text = [input]

            identify_obj["File Signatures"]["text"] = magic_numbers
            identify_obj["Regexes"]["text"] = self.regex_id.check(text)


        for key, value in list(identify_obj["Regexes"].items()):
            # if matches value is empty, remove it from the dict
            if value == []:
                del identify_obj["Regexes"][key]

        return identify_obj
