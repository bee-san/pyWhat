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
        if languages:
            for i in languages:
                prob_language += (
                    f" [red]{i.lang}[/red] {round(i.prob * 100)}% probability"
                )

        to_out = ""
        if prob_language:
            to_out += f"[bold #D7Afff]Possible language (ISO-639-1 code):[/bold #D7Afff]{prob_language}.\n"

        if text["File Signatures"]:
            to_out += "\n"
            to_out += f"[bold #D7Afff]File Identified[/bold #D7Afff] with Magic Numbers {text['File Signatures']['ISO 8859-1']}."
            to_out += f"\n[bold #D7Afff]File Description:[/bold #D7Afff] {text['File Signatures']['Description']}."
            to_out += "\n"
        if to_out:
            console.print(to_out)

        to_out = ""

        if text["Regexes"]:
            to_out += "\n[bold #D7Afff]Possible Identification[/bold #D7Afff]"
            table = Table(
                show_header=True, header_style="bold #D7Afff", show_lines=True
            )
            table.add_column("Matched Text", overflow="fold")
            table.add_column("Identified as", overflow="fold")
            table.add_column("Description")
            for i in text["Regexes"]:
                matched = i["Matched"]
                name = i["Regex Pattern"]["Name"]
                description = None

                if "URL" in i["Regex Pattern"]:
                    description = (
                        "Click here to analyse in the browser "
                        + i["Regex Pattern"]["URL"]
                        + matched.replace(" ", "")
                    )
                
                if i["Regex Pattern"]["Description"]:
                    if description:
                        description = (
                            description + "\n" + i["Regex Pattern"]["Description"]
                        )
                    else:
                        description = i["Regex Pattern"]["Description"]
                if description:
                    table.add_row(
                        matched,
                        name,
                        description,
                    )
                else:
                    table.add_row(
                        matched,
                        name,
                        "None",
                    )
            console.print(to_out, table)

        if not text["Regexes"] and not text["Language"]:
            console.print(
                "[bold #D7Afff]Could not find anything of interest.[/bold #D7Afff]"
            )

        """
        # This is commented out because there's too many possible hash idenfications
        # This is fixed by https://github.com/HashPals/Name-That-Hash/issues/89
        if text["Hashes"]:
            to_out = "\n[bold #D7Afff]Hashes Identified[/bold #D7Afff]"
            table = Table(
                show_header=True, header_style="bold #D7Afff", show_lines=True
            )
            table.add_column("Matched Text")
            table.add_column("Possible Hash Type")
            table.add_column("Description")
            for hash_text in text["Hashes"].keys():
                for types in text["Hashes"][hash_text]:
                    table.add_row(
                        hash_text,
                        types["name"],
                        types["description"],
                    )
            console.print(to_out, table)
        """

    def print_json(self, text: dict):
        return json.dumps(text, indent=4)
