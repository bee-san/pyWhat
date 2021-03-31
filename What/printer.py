import json
from rich.console import Console
from rich.table import Table


class Printing:
    def __init__(self):
        pass

    def pretty_print(self, text: dict):
        console = Console(highlight=False)

        languages = text["Language"]

        # calculate probability of each language
        prob_language = ""
        for i in languages:
            prob_language += f" [red]{i.lang}[/red] {round(i.prob * 100)}% probability"

        to_out = ""
        to_out += f"[bold #D7Afff]Possible language (ISO-639-1 code):[/bold #D7Afff]{prob_language}.\n"
        if text["Regexes"]:
            to_out += f"\n[bold #D7Afff]Possible Identification[/bold #D7Afff]"
            table = Table(show_header=True, header_style="bold #D7Afff")
            table.add_column("Matched Text")
            table.add_column("Identified as")
            table.add_column("Description")
            for i in text["Regexes"]:
                table.add_row(
                    i["Matched"],
                    i["Regex Pattern"]["Name"],
                    i["Regex Pattern"]["Description"],
                )
            console.print(to_out, table)
            return 0
        console.print(to_out)

    def print_json(self, text: dict):
        return json.dumps(text, indent=4)
