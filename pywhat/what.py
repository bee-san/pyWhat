import sys

import click
from rich.console import Console

from pywhat import helper, identifier, printer
from pywhat.distribution import Distribution


def print_tags(ctx, opts, value):
    if value:
        tags = sorted(helper.AvailableTags().get_tags())
        console = Console()
        console.print("[bold #D7Afff]" + "\n".join(tags) + "[/bold #D7Afff]")
        sys.exit()


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("text_input", required=True)
@click.option("--tags", is_flag=True, expose_value=False, callback=print_tags, help="Show available tags and exit.")
@click.option("--rarity", help="Filter by rarity.")
@click.option("--include_tags", help="Only print entries with included tags.")
@click.option("--exclude_tags", help="Exclude tags.")
def main(text_input, rarity, include_tags, exclude_tags):
    """
    What - Identify what something is.\n

    Made by Bee https://twitter.com/bee_sec_san\n

    https://github.com/bee-san\n

    Filtration:\n
        --rarity min:max\n
            Only print entries with rarity in range [min,max]. min and max can be omitted.\n
        --include_tags list\n
            Only include entries containing at least one tag in a list. List is a comma separated list.\n
        --include_tags list\n
            Exclude specified tags. List is a comma separated list.\n

    Examples:

        * what "HTB{this is a flag}"

        * what "0x52908400098527886E0F7030069857D2E4169EE7"

        * what -- 52.6169586, -1.9779857

        * what --rarity 0.6: myEmail@host.org

    Your text must either be in quotation marks, or use the POSIX standard of "--" to mean "anything after -- is textual input".

    """

    min_rarity = 0
    max_rarity = 1
    included_tags = []
    excluded_tags = []

    if rarity is not None:
        rarities = rarity.split(":")
        if len(rarities) != 2:
            print("Invalid rarity range format ('min:max' expected)")
            sys.exit(1)
        try:
            if not rarities[0].isspace() and rarities[0]:
                min_rarity = float(rarities[0])
            if not rarities[1].isspace() and rarities[1]:
                max_rarity = float(rarities[1])
        except ValueError:
            print("Invalid rarity argument (float expected)")
            sys.exit(1)
    if include_tags is not None:
        included_tags = list(map(str.strip, include_tags.split(',')))
    if exclude_tags is not None:
        excluded_tags = list(map(str.strip, exclude_tags.split(',')))
    distribution = Distribution(
        {"Tags": included_tags, "ExcludeTags": excluded_tags,
        "MinRarity": min_rarity, "MaxRarity": max_rarity})
    what_obj = What_Object(distribution)
    identified_output = what_obj.what_is_this(text_input)

    p = printer.Printing()
    p.pretty_print(identified_output)


class What_Object:
    def __init__(self, distribution):
        self.id = identifier.Identifier(distribution)

    def what_is_this(
        self, text: str) -> dict:
        """
        Returns a Python dictionary of everything that has been identified
        """
        return self.id.identify(text)


if __name__ == "__main__":
    main()
