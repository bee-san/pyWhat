from regex_identifier import RegexIdentifier
from languageDetector import LanguageDetector


class Identifier:
    def __init__(self):
        self.regex_id = RegexIdentifier()
        self.lang_detect = LanguageDetector()

    def identify(self, text: str) -> dict:
        identify_obj = {}
        identify_obj["Language"] = self.lang_detect.detect_what_lang(text)
        identify_obj["Regexes"] = self.regex_id.check(text)

        return identify_obj
