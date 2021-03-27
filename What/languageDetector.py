from langdetect import detect

class LanguageDetector:
    def detect_what_lang(self, text):
        return detect(text)