from langdetect import detect_langs
import langdetect


class LanguageDetector:
    def detect_what_lang(self, text):
        try:
            return detect_langs(text)
        except langdetect.lang_detect_exception.LangDetectException as e:
            return None
