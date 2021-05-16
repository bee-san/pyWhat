from PyWhat import languageDetector


def test_regex_successfully_parses():
    r = languageDetector.LanguageDetector()
    result = r.detect_what_lang(
        "Hello my name is Bee and this is a good example of English test!!".split(" ")
    )
    assert result[0].lang == "en"


def test_regex_successfully_parses_german():
    r = languageDetector.LanguageDetector()
    result = r.detect_what_lang(
        "Hallo, mein Name ist Biene und dies ist ein Beispiel für deutschen Text".split(
            " "
        )
    )
    assert result[0].lang == "de"
