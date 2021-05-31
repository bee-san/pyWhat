import sys

import click
from rich.console import Console

from pywhat import identifier, printer


def print_tags(ctx, opts, value):
    if value:
        id = identifier.Identifier()
        console = Console()
        console.print("[bold #D7Afff]" + "\n".join(id.tags) + "[/bold #D7Afff]")
        sys.exit()


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("text_input", required=True)
@click.option("--tags", is_flag=True, expose_value=False, callback=print_tags, help="Show available tags and exit.")
@click.option("--rarity")
@click.option("--include_tags")
@click.option("--exclude_tags")
def main(text_input, rarity, include_tags, exclude_tags):
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
    min_rarity = 0
    max_rarity = 1
    included_tags = None
    excluded_tags = None

    if rarity is not None:
        rarities = rarity.split(":")
        if len(rarities) != 2:
            print("Invalid rarity range format ('min:max' expected)")
            sys.exit(1)
        if not rarities[0].isspace() and rarities[0]:
            min_rarity = float(rarities[0])
        if not rarities[1].isspace() and rarities[1]:
            max_rarity = float(rarities[1])

    if include_tags is not None:
        included_tags = list(map(str.strip, include_tags.split(',')))
    if exclude_tags is not None:
        excluded_tags = list(map(str.strip, exclude_tags.split(',')))

    what_obj = What_Object()
    identified_output = what_obj.what_is_this(
        text_input, min_rarity, max_rarity, included_tags, excluded_tags)

    p = printer.Printing()
    p.pretty_print(identified_output)


class What_Object:
    def __init__(self):
        self.id = identifier.Identifier()

    def what_is_this(
        self, text: str,
        min_rarity, max_rarity, included_tags, excluded_tags) -> dict:
        """
        Returns a Python dictionary of everything that has been identified
        """
        return self.id.identify(
            text,
            min_rarity=min_rarity, max_rarity=max_rarity,
            included_tags=included_tags, excluded_tags=excluded_tags)


if __name__ == "__main__":
    main()
