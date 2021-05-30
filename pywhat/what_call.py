import pywhat.regex_identifier


def export_cli(text):
    ident = pywhat.regex_identifier.RegexIdentifier()
    return ident.check(text)
