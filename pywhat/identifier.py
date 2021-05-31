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

    def identify(self, text: str, api=False) -> dict:
        identify_obj = {}
        magic_numbers = {}
        file_text = {}

        def get_file_data(filepath):
            short_name = os.path.basename(filepath)
            magic_numbers[short_name] = self.file_sig.open_binary_scan_magic_nums(filepath)
            file_text[short_name] = self.file_sig.open_file_loc(filepath)

            # if file doesn't exist, check to see if the inputted text is
            # a file in hex format
            if not magic_numbers[short_name]:
                magic_numbers[short_name] = self.file_sig.check_magic_nums(filepath)


        if os.path.isdir(text):
            # if input is a directory, recursively search for all of the files
            for myfile in glob.iglob(text + "**/**", recursive=True):
                if os.path.isfile(myfile):
                    get_file_data(myfile)

        elif os.path.isfile(text):
            get_file_data(text)

        else:
            file_text["None"] = [text]

        identify_obj["File Signatures"] = magic_numbers
        identify_obj["Regexes"] = self.regex_id.check(file_text)
        # get_hashes takes a list of hashes, we split to give it a list
        # identify_obj["Hashes"] = self.name_that_hash.get_hashes(text.split())

        return identify_obj
