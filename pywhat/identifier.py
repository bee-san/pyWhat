from pywhat.regex_identifier import RegexIdentifier
from pywhat.magic_numbers import FileSignatures
from pywhat.nameThatHash import Nth
import os.path
import glob

class Identifier:
    def __init__(self):
        self.regex_id = RegexIdentifier()
        self.file_sig = FileSignatures()
        self.name_that_hash = Nth()

    def identify(self, text: str, api=False) -> dict:
        identify_obj = {}
        magic_numbers = {}
        file_text = []

        if not api and (os.path.isdir(text) == True or os.path.isfile(text) == True):
            if os.path.isdir(text):
                # if input is a directory, recursively search for all of the files
                # and append each content of a file to file_text

                for myfile in glob.iglob(text + "**/**", recursive=True):
                    if os.path.isfile(myfile):
                        magic_numbers[myfile] = self.file_sig.open_binary_scan_magic_nums(myfile)
                        file_text.append(self.file_sig.open_file_loc(myfile))

            if os.path.isfile(text):
                # if input is a file
                magic_numbers[text] = self.file_sig.open_binary_scan_magic_nums(text)
                file_text.append(self.file_sig.open_file_loc(text))

            # flatten file_text as it may be a nested list
            clean_list = []
            for item in file_text:
                clean_list.extend(item)

        else:
            clean_list = [text]


        for key, value in magic_numbers.items():
            # If file doesn't exist, check to see if the inputted text is
            # a file in hex format
            if not value:
                value = self.file_sig.check_magic_nums(key)
        identify_obj["File Signatures"] = magic_numbers

        identify_obj["Regexes"] = self.regex_id.check(clean_list)
        # get_hashes takes a list of hashes, we split to give it a list
        # identify_obj["Hashes"] = self.name_that_hash.get_hashes(text.split())

        return identify_obj
