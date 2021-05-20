import click
from pywhat import identifier, printer


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("text_input", required=True)
def main(text_input):
    """
    What - Identify what something is.\n

    Made by Bee https://twitter.com/bee_sec_san\n

    https://github.com/bee-san\n

    Examples:

        * what "HTB{this is a flag}"

        * what "0x52908400098527886E0F7030069857D2E4169EE7"

        * what -- 52.6169586, -1.9779857

    Your text must either be in quotation marks, or use the POSIX standard of "--" to mean "anything after -- is textual input".

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


if __name__ == "__main__":
    main()
