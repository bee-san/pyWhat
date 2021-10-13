import json
import os
import re

from rich.console import Console
from rich.table import Table


class Printing:
    def __init__(self):
        self.console = Console(highlight=False)
        self.bug_bounty_mode = False

    def pretty_print(self, text: dict, text_input, print_tags=False):
        to_out = ""

        if text["File Signatures"]:
            for key, value in text["File Signatures"].items():
                if value:
                    to_out += "\n"
                    to_out += f"[bold #D7Afff]File Identified[/bold #D7Afff]: [bold]{key}[/bold] with Magic Numbers {value['ISO 8859-1']}."
                    to_out += f"\n[bold #D7Afff]File Description: [/bold #D7Afff] {value['Description']}."
                    to_out += "\n\n"

        if text["Regexes"]:
            to_out += "\n[bold #D7Afff]Possible Identification[/bold #D7Afff]\n"
            table = Table(
                show_header=True, header_style="bold #D7Afff", show_lines=True
            )
            table.add_column("Matched Text", overflow="fold")
            table.add_column("Identified as", overflow="fold")
            table.add_column("Description", overflow="fold")

            if self._check_if_directory(text_input):
                # if input is a folder, add a filename column
                table.add_column("File", overflow="fold")

            # Check if there are any bug bounties with exploits
            # in the regex
            self._check_if_exploit_in_json(text)
            if self.bug_bounty_mode:
                table.add_column("Exploit", overflow="fold")

            for key, value in text["Regexes"].items():
                for i in value:
                    matched = i["Matched"]
                    name = i["Regex Pattern"]["Name"]
                    description = None
                    filename = key
                    exploit = None

                    if "URL" in i["Regex Pattern"] and i["Regex Pattern"]["URL"]:
                        description = (
                            "Click here to analyse in the browser\n"
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

                    if (
                        "Exploit" in i["Regex Pattern"]
                        and i["Regex Pattern"]["Exploit"]
                    ):
                        exploit = i["Regex Pattern"]["Exploit"]

                    if print_tags:
                        tags = f"Tags: {', '.join(i['Regex Pattern']['Tags'])}"
                        if description is None:
                            description = tags
                        else:
                            description += "\n" + tags

                    if description is None:
                        description = "None"

                    # FIXME this is quite messy
                    if self.bug_bounty_mode:
                        if self._check_if_directory(text_input):
                            table.add_row(
                                matched,
                                name,
                                description,
                                filename,
                                exploit,
                            )
                        else:
                            table.add_row(
                                matched,
                                name,
                                description,
                                exploit,
                            )
                    elif self._check_if_directory(text_input):
                        table.add_row(
                            matched,
                            name,
                            description,
                            filename,
                        )
                    else:
                        table.add_row(
                            matched,
                            name,
                            description,
                        )

            self.console.print(to_out.strip(), table)

        elif not self.bug_bounty_mode:
            self.console.print((to_out + "\nNothing found!").lstrip())

    def print_json(self, text: dict):
        self.console.print(json.dumps(text))

    """
    Does not create a table, prints it as raw text
    Returns the printable object
    """

    def print_raw(self, text: dict, text_input, print_tags=False):
        output_str = ""

        if text["File Signatures"] and text["Regexes"]:
            for key, value in text["File Signatures"].items():
                if value:
                    output_str += "\n"
                    output_str += f"[bold #D7Afff]File Identified[/bold #D7Afff]: [bold]{key}[/bold] with Magic Numbers {value['ISO 8859-1']}."
                    output_str += f"\n[bold #D7Afff]File Description:[/bold #D7Afff] {value['Description']}."
                    output_str += "\n"

        if text["Regexes"]:
            for key, value in text["Regexes"].items():
                for i in value:
                    description = None
                    matched = i["Matched"]
                    if self._check_if_directory(text_input):
                        output_str += f"[bold #D7Afff]File: {key}[/bold #D7Afff]\n"
                    output_str += (
                        "[bold #D7Afff]Matched on: [/bold #D7Afff]" + i["Matched"]
                    )
                    output_str += (
                        "\n[bold #D7Afff]Name: [/bold #D7Afff]"
                        + i["Regex Pattern"]["Name"]
                    )

                    link = None
                    if "URL" in i["Regex Pattern"] and i["Regex Pattern"]["URL"]:
                        link = (
                            "\n[bold #D7Afff]Link: [/bold #D7Afff] "
                            + i["Regex Pattern"]["URL"]
                            + matched.replace(" ", "")
                        )

                    if link:
                        output_str += link

                    if i["Regex Pattern"]["Description"]:
                        description = (
                            "\n[bold #D7Afff]Description: [/bold #D7Afff]"
                            + i["Regex Pattern"]["Description"]
                        )

                    if description:
                        output_str += description

                    if (
                        "Exploit" in i["Regex Pattern"]
                        and i["Regex Pattern"]["Exploit"]
                    ):
                        output_str += (
                            "\n[bold #D7Afff]Exploit: [/bold #D7Afff]"
                            + i["Regex Pattern"]["Exploit"]
                        )

                    if print_tags:
                        output_str += f"\n[bold #D7Afff]Tags: [/bold #D7Afff]{', '.join(i['Regex Pattern']['Tags'])}"

                    output_str += "\n\n"

        if output_str == "" and not self.bug_bounty_mode:
            self.console.print("Nothing found!")

        if output_str.strip():
            self.console.print(output_str.rstrip())

        return output_str

    def format_print(self, text: dict, format_str: str):
        if text["Regexes"]:
            output = []
            format_list = []

            # Split format_str so that format_list's item will either be r'\\' or something else
            start = 0
            i = format_str.find(r"\\", start)
            while i != -1:
                if format_str[start:i]:
                    format_list.append(format_str[start:i])
                format_list.append("\\")
                start = i + 2
                i = format_str.find(r"\\", start)
            format_list.append(format_str[start:])

            for key, value in text["Regexes"].items():
                for match in value:
                    temp = ""
                    for s in format_list:
                        formats = {
                            "%m": match["Matched"],
                            "%n": match["Regex Pattern"]["Name"],
                            "%d": match["Regex Pattern"]["Description"],
                            "%e": match["Regex Pattern"].get("Exploit"),
                            "%r": str(match["Regex Pattern"]["Rarity"]),
                            "%l": match["Regex Pattern"]["URL"] + match["Matched"]
                            if match["Regex Pattern"]["URL"] is not None
                            else None,
                            "%t": ", ".join(match["Regex Pattern"]["Tags"]),
                        }
                        for format, value in formats.items():
                            value = str() if value is None else value
                            s = re.sub(r"(?<!\\)" + format, value, s)
                        s = re.sub(r"\\%", "%", s)
                        temp += s
                    output.append(temp)

            str_output = "\n".join(output)
            if str_output.strip():
                self.console.print(str_output)

    def _check_if_exploit_in_json(self, text: dict) -> bool:
        if "File Signatures" in text and text["File Signatures"]:
            # loops files
            for file in text["Regexes"].keys():
                for i in text["Regexes"][file]:
                    if "Exploit" in i.keys():
                        self.bug_bounty_mode = True
        else:
            for value in text["Regexes"]["text"]:
                if "Exploit" in value["Regex Pattern"].keys():
                    self.bug_bounty_mode = True

        return self.bug_bounty_mode

    def _check_if_directory(self, text_input):
        return os.path.isdir(text_input)
