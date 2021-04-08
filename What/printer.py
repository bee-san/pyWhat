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
                prob_language += f" [red]{i.lang}[/red] {round(i.prob * 100)}% probability"

        to_out = ""
        if prob_language:
            to_out += f"[bold #D7Afff]Possible language (ISO-639-1 code):[/bold #D7Afff]{prob_language}.\n"

        if text["File Signatures"]:
            to_out += "\n"
            to_out += f"[bold #D7Afff]File Identified[/bold #D7Afff] with Magic Numbers {text['File Signatures']['ISO 8859-1']}."
            to_out += f"\n[bold #D7Afff]File Description:[/bold #D7Afff] {text['File Signatures']['Description']}."
            to_out += "\n"

        if text["Regexes"]:
            to_out += f"\n[bold #D7Afff]Possible Identification[/bold #D7Afff]"
            table = Table(show_header=True, header_style="bold #D7Afff", show_lines=True)
            table.add_column("Matched Text")
            table.add_column("Identified as")
            table.add_column("Description")
            for i in text["Regexes"]:
                matched = i["Matched"]
                name = i["Regex Pattern"]["Name"]
                description = self.get_crypto_links(name, matched)
                if not description:
                    description = i["Regex Pattern"]["Description"]
                table.add_row(
                    matched,
                    name,
                    description,
                )
            console.print(to_out, table)
            return 0
        console.print(to_out)

    def print_json(self, text: dict):
        return json.dumps(text, indent=4)

    def get_crypto_links(self, text, matched):
        explorers = {
            "Ethereum Wallet": "https://etherscan.io/address/",
            "Dogecoin Wallet Address": "https://dogechain.info/address/",
            "Bitcoin Wallet": "https://www.blockchain.com/btc/address/"
        }
        if text in explorers:
            return "Click here to see the address on the blockchain " + explorers[text] + matched
        return None

        
