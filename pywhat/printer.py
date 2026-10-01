import json
import os
import re
from typing import Dict, Iterable, Optional, Tuple

from rich.console import Console
from rich.table import Table


def get_link(match: dict) -> Optional[str]:
    """
    The link to analyse a match in the browser, or None if there is none: the
    "Link" that a processor gave the match, such as the OpenStreetMap link of
    coordinates (issue #263), otherwise the "URL" of its regex followed by the
    matched text without spaces.
    """
    regex = match["Regex Pattern"]
    if regex.get("Link"):
        return regex["Link"]
    if regex.get("URL"):
        return regex["URL"] + match["Matched"].replace(" ", "")
    return None


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

            show_files = self._show_files(text, text_input)
            if show_files:
                # if input is a folder or several inputs, add a filename column
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

                    link = get_link(i)
                    if link:
                        description = "Click here to analyse in the browser\n" + link

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
                        if show_files:
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
                    elif show_files:
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
        # Not self.console.print(): rich wraps lines at the width of the
        # terminal, even when stdout is a pipe, and treats "[...]" as markup
        # and ":name:" as emoji codes, which breaks the JSON (issue #264).
        # json.dumps() escapes line breaks and non-ASCII characters, so this
        # is one line of ASCII, valid JSON whatever the encoding of stdout.
        print(json.dumps(text))

    """
    Does not create a table, prints it as raw text
    Returns the printable object
    """

    def print_raw(self, text: dict, text_input, print_tags=False, show_files=None):
        output_str = ""

        if text["File Signatures"] and text["Regexes"]:
            for key, value in text["File Signatures"].items():
                if value:
                    output_str += self._raw_signature(key, value)

        if text["Regexes"]:
            if show_files is None:
                show_files = self._show_files(text, text_input)
            for key, value in text["Regexes"].items():
                for i in value:
                    description = None
                    if show_files:
                        output_str += f"[bold #D7Afff]File: {key}[/bold #D7Afff]\n"
                    output_str += (
                        "[bold #D7Afff]Matched on: [/bold #D7Afff]" + i["Matched"]
                    )
                    output_str += (
                        "\n[bold #D7Afff]Name: [/bold #D7Afff]"
                        + i["Regex Pattern"]["Name"]
                    )

                    link = get_link(i)
                    if link:
                        output_str += "\n[bold #D7Afff]Link: [/bold #D7Afff] " + link

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
                            "%l": get_link(match),
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

    def print_stream(
        self,
        found: Iterable[Tuple[str, str, dict]],
        text_input,
        print_tags=False,
        format_str: Optional[str] = None,
        json_output=False,
    ):
        """
        Print what Identifier.iter_identify() finds as soon as it is found
        (issue #189), instead of everything once the search is complete.

        Every match and file signature is printed like print_raw() prints it
        or, with format_str, every match like format_print() does. With
        json_output, every match and file signature is a JSON object of its
        own, on one line (JSON Lines), in the format of print_json(), e.g.
        {"File Signatures": null, "Regexes": {"text": [match]}}.
        """
        if json_output:
            for kind, location, value in found:
                line: Dict[str, Optional[dict]] = {
                    "File Signatures": None,
                    "Regexes": None,
                }
                line[kind] = {location: [value] if kind == "Regexes" else value}
                # The console, not print(), so that progress bars on the same
                # terminal stay below the output. soft_wrap does not break the
                # lines.
                self.console.print(
                    json.dumps(line),
                    markup=False,
                    emoji=False,
                    highlight=False,
                    soft_wrap=True,
                )
            return

        show_files = self._show_files_of_inputs(text_input)
        previous = None  # (kind, location) of what was printed last
        found_matches = False
        for kind, location, value in found:
            if kind == "File Signatures":
                if format_str is None:
                    # With an empty line before it, like print_raw()
                    self.console.print(self._raw_signature(location, value).rstrip())
                    previous = (kind, location)
                continue
            found_matches = True
            match = {"File Signatures": None, "Regexes": {location: [value]}}
            if format_str is not None:
                self.format_print(match, format_str)
            else:
                # An empty line between the matches, like print_raw(), but not
                # between a file signature and the matches in the file
                if previous is not None and previous != ("File Signatures", location):
                    self.console.print()
                self.print_raw(match, text_input, print_tags, show_files=show_files)
            previous = (kind, location)

        if not found_matches and format_str is None:
            self.console.print("Nothing found!")

    def _raw_signature(self, location: str, signature: dict) -> str:
        """A file signature as print_raw() prints it, with markup."""
        return (
            "\n"
            f"[bold #D7Afff]File Identified[/bold #D7Afff]: [bold]{location}[/bold] with Magic Numbers {signature['ISO 8859-1']}."
            f"\n[bold #D7Afff]File Description:[/bold #D7Afff] {signature['Description']}."
            "\n"
        )

    def _check_if_exploit_in_json(self, text: dict) -> bool:
        # The matches are under "text" for text, and under the file names for
        # a file or a directory (with or without file signatures)
        for matches in text["Regexes"].values():
            for match in matches:
                if "Exploit" in match["Regex Pattern"]:
                    self.bug_bounty_mode = True

        return self.bug_bounty_mode

    def _check_if_directory(self, text_input):
        return os.path.isdir(text_input)

    def _show_files(self, text: dict, text_input) -> bool:
        """
        Whether to show the file of every match: if text_input is a directory,
        or if it is a list or tuple of several inputs (issue #171) and some of
        the matches are in files, not only in text.
        """
        if isinstance(text_input, str):
            return self._check_if_directory(text_input)
        if len(text_input) == 1:
            return self._check_if_directory(text_input[0])
        return any(location != "text" for location in text["Regexes"] or ())

    def _show_files_of_inputs(self, text_input) -> bool:
        """
        Like _show_files(), but before anything is found, for print_stream():
        if text_input is a directory, or several inputs of which a file or a
        directory is one.
        """
        if isinstance(text_input, str):
            return self._check_if_directory(text_input)
        if len(text_input) == 1:
            return self._check_if_directory(text_input[0])
        return any(os.path.exists(text) for text in text_input)
