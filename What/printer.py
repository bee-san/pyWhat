import json


class Printing:
    def __init__(self):
        pass

    def pretty_print(self, text: dict):
        to_out = ""
        to_out += f"Possible language: {text['Language']}.\n"
        if text["Regexes"]:
            to_out += f"Possible Identification:\n"
            for i in text["Regexes"]:
                to_out += f'"{i["Matched"]}" is possibly {i["Regex Pattern"]["Name"]} - {i["Regex Pattern"]["Description"]}\n'
        print(to_out)

    def print_json(self, text: dict):
        return json.dumps(text, indent=4)
