from PyWhat.regex_identifier import RegexIdentifier
from PyWhat.languageDetector import LanguageDetector
from PyWhat.magic_numbers import FileSignatures
from PyWhat.nameThatHash import Nth
import os.path


class Identifier:
    def __init__(self):
        self.regex_id = RegexIdentifier()
        self.lang_detect = LanguageDetector()
        self.file_sig = FileSignatures()
        self.name_that_hash = Nth()

    def identify(self, text: str) -> dict:
        identify_obj = {}

        magic_numbers = None
        if self.file_exists(text):
            magic_numbers = self.file_sig.open_binary_scan_magic_nums(text)
            text = self.file_sig.open_file_loc(text)
            identify_obj["File Signatures"] = magic_numbers

        if not magic_numbers:
            # If file doesn't exist, check to see if the inputted text is
            # a file in hex format
            identify_obj["File Signatures"] = self.file_sig.check_magic_nums(text)

        identify_obj["Language"] = self.lang_detect.detect_what_lang(text)
        identify_obj["Regexes"] = self.regex_id.check(text)
        # get_hashes takes a list of hashes, we split to give it a list
        identify_obj["Hashes"] = self.name_that_hash.get_hashes(text.split())
        print("\n")
        print(identify_obj["Hashes"])
        print("\n")

        return identify_obj

    def file_exists(self, text):
        return os.path.isfile(text)
