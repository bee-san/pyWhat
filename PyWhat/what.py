import os

import click
from PyWhat import identifier, printer


@click.command()
@click.argument("text_input", required=True)
def main(text_input):
    """
    What - Identify what something is.\n
    Made by Bee https://twitter.com/bee_sec_san
    https://github.com/bee-san\n

    Examples:

        * what "HTB{this is a flag}"

        * what "0x52908400098527886E0F7030069857D2E4169EE7"


    """

    what_obj = What_Object()
    identified_output = what_obj.what_is_this(text_input)

    p = printer.Printing()
    p.pretty_print(identified_output)


class What_Object:
    def __init__(self):
        self.id = identifier.Identifier()

    def what_is_this(self, text: str) -> dict:
        """
        Returns a Python dictionary of everything that has been identified
        """
        return self.id.identify(text)


os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    main()
