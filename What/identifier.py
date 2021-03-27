from what.regex_identifier import RegexIdentifier
from what.languageDetector import LanguageDetector
class Identifier:
    def __init__(self):
        self.regex_id = RegexIdentifier()
        self.lang_detect = LanguageDetector()
    