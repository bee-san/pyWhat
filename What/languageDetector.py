from langdetect import detect_langs


class LanguageDetector:
    def detect_what_lang(self, text):
        return detect_langs(text)
