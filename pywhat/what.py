import sys

import click
from rich.console import Console

from pywhat import __version__, identifier, printer
from pywhat.filter import Distribution, Filter
from pywhat.helper import AvailableTags, InvalidTag, Keys, str_to_key
from pywhat.interactive import InteractiveShell, query_from_options


def print_tags(ctx, opts, value):
    if value:
        tags = sorted(AvailableTags().get_tags())
        console = Console()
        console.print("[bold #D7AFFF]" + "\n".join(tags) + "[/bold #D7AFFF]")
        sys.exit()


def print_version(ctx, opts, value):
    if value:
        console = Console()
        console.print(f"PyWhat version [bold #49C3CE]{__version__}[/bold #49C3CE]")
        sys.exit()


def create_filter(rarity, include, exclude):
    filters_dict = {}
    if rarity is not None:
        rarities = rarity.split(":")
        if len(rarities) != 2:
            print("Invalid rarity range format ('min:max' expected)")
            sys.exit(1)
        try:
            if not rarities[0].isspace() and rarities[0]:
                filters_dict["MinRarity"] = float(rarities[0])
            if not rarities[1].isspace() and rarities[1]:
                filters_dict["MaxRarity"] = float(rarities[1])
        except ValueError:
            print("Invalid rarity argument (float expected)")
            sys.exit(1)
    if include is not None:
        filters_dict["Tags"] = list(map(str.strip, include.split(",")))
    if exclude is not None:
        filters_dict["ExcludeTags"] = list(map(str.strip, exclude.split(",")))

    try:
        filter = Filter(filters_dict)
    except InvalidTag:
        print(
            "Passed tags are not valid.\n"
            "You can check available tags by using: 'pywhat --tags'"
        )
        sys.exit(1)

    return filter


def get_text(ctx, opts, value):
    # In interactive mode, stdin is where the commands come from
    if (
        not value
        and not ctx.params.get("interactive")
        and not click.get_text_stream("stdin").isatty()
    ):
        return click.get_text_stream("stdin").read().strip()
    return value


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("text_input", callback=get_text, required=False)
@click.option(
    "-t",
    "--tags",
    is_flag=True,
    expose_value=False,
    callback=print_tags,
    help="Show available tags and exit.",
)
@click.option(
    "-r",
    "--rarity",
    help="Filter by rarity. Rarity is how unlikely something is to be a false-positive. The higher the number, the more unlikely. This is in the range of 0:1. To filter only items past 0.5, use 0.5: with the colon on the end. Default 0.1:1",
    default="0.1:1",
)
@click.option("-i", "--include", help="Only show matches with these tags.")
@click.option("-e", "--exclude", help="Exclude matches with these tags.")
@click.option("-o", "--only-text", is_flag=True, help="Do not scan files or folders.")
@click.option("-k", "--key", help="Sort by the specified key.")
@click.option("--reverse", is_flag=True, help="Sort in reverse order.")
@click.option(
    "-br",
    "--boundaryless-rarity",
    help="Same as --rarity but for boundaryless mode (toggles what regexes will not have boundaries).",
    default="0.1:1",
)
@click.option(
    "-bi", "--boundaryless-include", help="Same as --include but for boundaryless mode."
)
@click.option(
    "-be", "--boundaryless-exclude", help="Same as --exclude but for boundaryless mode."
)
@click.option(
    "-db", "--disable-boundaryless", is_flag=True, help="Disable boundaryless mode."
)
@click.option(
    "-dp",
    "--disable-processing",
    is_flag=True,
    help="Disable the processing of matches, e.g. adding dates to Unix timestamps.",
)
@click.option("--json", is_flag=True, help="Return results in json format.")
@click.option(
    "--interactive",
    is_flag=True,
    is_eager=True,  # get_text() needs to know about it
    help="Load the input into memory and search through the matches interactively.",
)
@click.option(
    "-v",
    "--version",
    is_flag=True,
    callback=print_version,
    help="Display the version of pywhat.",
)
@click.option(
    "-if",
    "--include-filenames",
    is_flag=True,
    help="Search filenames for possible matches.",
)
@click.option(
    "--format",
    required=False,
    help="Format output according to specified rules.",
)
@click.option("-pt", "--print-tags", is_flag=True, help="Add flags to output")
def main(**kwargs):
    """
    pyWhat - Identify what something is.

    Made by Bee https://twitter.com/bee_sec_san

    https://github.com/bee-san

    Filtration:

        --rarity min:max

            Rarity is how unlikely something is to be a false-positive. The higher the number, the more unlikely.

            Only print entries with rarity in range [min,max]. min and max can be omitted.

            Note: PyWhat by default has a rarity of 0.1. To see all matches, with many potential false positives use `0:`.

        --include list

            Only include entries containing at least one tag in a list. List is a comma separated list.

        --exclude list

            Exclude specified tags. List is a comma separated list.

    Sorting:

        --key key_name

            Sort by the given key.

        --reverse

            Sort in reverse order.

        Available keys:

            name - Sort by the name of regex pattern

            rarity - Sort by rarity

            matched - Sort by a matched string

            none - No sorting is done (the default)

    Exporting:

        --json

            Return results in json format.

    Boundaryless mode:

        CLI tool matches strings like 'abcdTHM{hello}plze' by default because the boundaryless mode is enabled for regexes with a rarity of 0.1 and higher.

        Since boundaryless mode may produce a lot of false-positive matches, it is possible to disable it, either fully or partially.

        '--disable-boundaryless' flag can be used to fully disable this mode.

        In addition, '-br', '-bi', and '-be' options can be used to tweak which regexes should be in boundaryless mode.

        Refer to the Filtration section for more information.

    Processing:

        Matches are processed further once a regex has found them. For example, the date of a Unix timestamp, in UTC, is added to its description: pywhat --rarity 0: --include "UNIX Timestamp" 1637093119

        '--disable-processing' flag can be used to show the matches as the regexes found them.

    Formatting the output:

        --format format_str

            format_str can be equal to:

                pretty - Output data in the table

                json - Output data in json format

                CUSTOM_STRING - Print data in the way you want. For every match CUSTOM_STRING will be printed and '%x' (See below for possible x values) will be substituted with a match value.

                For example:

                    pywhat --format '%m - %n' 'google.com htb{flag}'

                    will print:

                    htb{flag} - HackTheBox Flag Format
                    google.com - Uniform Resource Locator (URL)

                Possible '%x' values:

                    %m - matched text

                    %n - name of regex

                    %d - description (will not output if absent)

                    %e - exploit (will not output if absent)

                    %r - rarity

                    %l - link (will not output if absent)

                    %t - tags (in 'tag1, tag2 ...' format)

                If you want to print '%' or '\\' character - escape it: '\\%', '\\\\'.

    Interactive mode:

        --interactive

            Identify the input once, keep the matches in memory and search through them as often as you like, with searches such as 'include:"Bug Bounty", rarity:"0.5:"'.

            The --rarity, --include and --exclude options are the search to start with, the other options work as usual. The input is optional, the 'load' command loads a file, directory or text. Type 'help' in interactive mode to see all commands.

    Examples:

        * what 'HTB{this is a flag}'

        * what '0x52908400098527886E0F7030069857D2E4169EE7'

        * what -- '52.6169586, -1.9779857'

        * what --rarity 0.6: 'myEmail@host.org'

        * what --rarity 0: --include "credentials" --exclude "aws" 'James:SecretPassword'

        * what -br 0.6: -be URL '123myEmail@host.org456'

    Your text must either be in quotation marks, or use the POSIX standard of "--" to mean "anything after -- is textual input".


    pyWhat can also search files or even a whole directory with recursion:

        * what 'secret.txt'

        * what 'this/is/a/path'

        * what --interactive 'this/is/a/path'

    """
    if kwargs["text_input"] is None and not kwargs["interactive"]:
        sys.exit("Text input expected. Run 'pywhat --help' for help")
    dist = Distribution(
        create_filter(kwargs["rarity"], kwargs["include"], kwargs["exclude"])
    )
    if kwargs["disable_boundaryless"]:
        boundaryless = Filter({"Tags": []})  # use empty filter
    else:
        boundaryless = create_filter(
            kwargs["boundaryless_rarity"],
            kwargs["boundaryless_include"],
            kwargs["boundaryless_exclude"],
        )
    # processors=None uses the default processors, [] disables processing
    processors = [] if kwargs["disable_processing"] else None
    what_obj = What_Object(dist, processors)
    if kwargs["key"] is None:
        key = Keys.NONE
    else:
        try:
            key = str_to_key(kwargs["key"])
        except ValueError:
            print("Invalid key")
            sys.exit(1)
    if kwargs["interactive"]:
        InteractiveShell(
            query_from_options(kwargs["rarity"], kwargs["include"], kwargs["exclude"]),
            boundaryless=boundaryless,
            only_text=kwargs["only_text"],
            include_filenames=kwargs["include_filenames"],
            processors=processors,
            key=key,
            reverse=kwargs["reverse"],
            json_output=kwargs["json"],
            format_str=kwargs["format"],
            print_tags=kwargs["print_tags"],
        ).run(kwargs["text_input"])
        return
    identified_output = what_obj.what_is_this(
        kwargs["text_input"],
        kwargs["only_text"],
        key,
        kwargs["reverse"],
        boundaryless,
        kwargs["include_filenames"],
    )

    p = printer.Printing()

    if kwargs["json"] or str(kwargs["format"]).strip() == "json":
        p.print_json(identified_output)
    elif str(kwargs["format"]).strip() == "pretty":
        p.pretty_print(identified_output, kwargs["text_input"], kwargs["print_tags"])
    elif kwargs["format"] is not None:
        p.format_print(identified_output, kwargs["format"])
    else:
        p.print_raw(identified_output, kwargs["text_input"], kwargs["print_tags"])


class What_Object:
    def __init__(self, distribution, processors=None):
        self.id = identifier.Identifier(dist=distribution, processors=processors)

    def what_is_this(
        self,
        text: str,
        only_text: bool,
        key,
        reverse: bool,
        boundaryless: Filter,
        include_filenames: bool,
    ) -> dict:
        """
        Returns a Python dictionary of everything that has been identified
        """
        return self.id.identify(
            text,
            only_text=only_text,
            key=key,
            reverse=reverse,
            boundaryless=boundaryless,
            include_filenames=include_filenames,
        )


if __name__ == "__main__":
    main()
