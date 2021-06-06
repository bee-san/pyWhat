import json

from rich.console import Console
from rich.table import Table


class Printing:
    def pretty_print(self, text: dict):
        console = Console(highlight=False)

        to_out = ""

        if text["File Signatures"] and text["Regexes"]:
            to_out += "\n"
            to_out += f"[bold #D7Afff]File Identified[/bold #D7Afff] with Magic Numbers {text['File Signatures']['ISO 8859-1']}."
            to_out += f"\n[bold #D7Afff]File Description:[/bold #D7Afff] {text['File Signatures']['Description']}."
            to_out += "\n"

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
        if to_out == "":
            console.print("Nothing found!")

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
