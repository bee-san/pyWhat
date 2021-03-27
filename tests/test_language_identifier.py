from What import languageDetector

def test_regex_successfully_parses():
    r = languageDetector.LanguageDetector()
    result = r.detect_what_lang("Hello my name is Bee!")
    assert result == "en"