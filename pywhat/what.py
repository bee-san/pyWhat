import sys
from typing import Any, Callable, Iterator, List, Optional, Sequence, Union

import click
from rich.console import Console
from rich.markup import escape

from pywhat import __version__, identifier, printer
from pywhat.filter import Distribution, Filter
from pywhat.helper import (
    AvailableTags,
    InvalidTag,
    Keys,
    get_names,
    load_regexes,
    split_tags,
    str_to_key,
)
from pywhat.identifier import Found, Progress
from pywhat.interactive import InteractiveShell, query_from_options
from pywhat.processors import Processor, default_processors, verifiers
from pywhat.progress import progress_bars
from pywhat.ranking import located_matches, parse_top, top_matches
from pywhat.unicode import escape_unencodable, texts


def print_tags(ctx, opts, value):
    if value:
        tags = sorted(AvailableTags().get_tags())
        console = Console()
        console.print("[bold #D7AFFF]" + "\n".join(tags) + "[/bold #D7AFFF]")
        sys.exit()


def print_names(ctx, opts, value):
    """Print every regex name, followed by its alternative names (issue #184)."""
    if value:
        # Options are parsed before main() runs escape_unencodable(), and
        # names such as "Bitcoin (\u20bf) Wallet Address" are not ASCII
        escape_unencodable(sys.stdout)
        lines = []
        for regex in sorted(load_regexes(), key=lambda regex: regex["Name"].lower()):
            name, *alternative_names = get_names(regex)
            line = f"[bold #D7AFFF]{escape(name)}[/bold #D7AFFF]"
            if alternative_names:
                line += ": " + escape(", ".join(alternative_names))
            lines.append(line)
        # One line per regex, also when the output is not a terminal
        Console(highlight=False).print("\n".join(lines), soft_wrap=True)
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
        filters_dict["Tags"] = list(map(str.strip, split_tags(include)))
    if exclude is not None:
        filters_dict["ExcludeTags"] = list(map(str.strip, split_tags(exclude)))

    try:
        filter = Filter(filters_dict)
    except InvalidTag:
        print(
            "Passed tags are not valid.\n"
            "You can check available tags by using: 'pywhat --tags'\n"
            "and the names of the regexes, which work like tags, by using: "
            "'pywhat --names'"
        )
        sys.exit(1)

    return filter


def get_text(ctx, opts, value):
    # The inputs, read from stdin if there are none. In interactive mode,
    # stdin is where the commands come from
    if (
        not any(value)
        and not ctx.params.get("interactive")
        and not click.get_text_stream("stdin").isatty()
    ):
        return (read_stdin(),)
    return value


def read_stdin() -> str:
    """
    Read the input from stdin like a file (see pywhat.unicode.texts), so that
    UTF-16 text and binary data can be piped in too. Input that is not UTF-8
    is decoded with the encoding of stdin, as it was before.
    """
    stdin = click.get_text_stream("stdin")
    try:
        data = click.get_binary_stream("stdin").read()
    except RuntimeError:  # stdin is a text stream without a binary buffer
        return stdin.read().strip()
    return "\n".join(texts(data, getattr(stdin, "encoding", None))).strip()


def print_left_out(shown: int, total: int) -> None:
    """
    Say how many matches --top left out. On stderr, so that the output (e.g.
    JSON) is the same as without --top.
    """
    if shown < total:
        Console(stderr=True, highlight=False, soft_wrap=True).print(
            f"\nShowing the {shown} most likely of {total} matches. Use --top to "
            "show more of them, or --interactive to search through all of them."
        )


@click.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("text_input", callback=get_text, nargs=-1)
@click.option(
    "-t",
    "--tags",
    is_flag=True,
    expose_value=False,
    callback=print_tags,
    help="Show available tags and exit.",
)
@click.option(
    "--names",
    is_flag=True,
    expose_value=False,
    callback=print_names,
    help="Show the names of the regexes, with their alternative names, and exit.",
)
@click.option(
    "-r",
    "--rarity",
    help="Filter by rarity. Rarity is how unlikely something is to be a false-positive. The higher the number, the more unlikely. This is in the range of 0:1. To filter only items past 0.5, use 0.5: with the colon on the end. Default 0.1:1",
    default="0.1:1",
)
@click.option("-i", "--include", help="Only show matches with these tags or names.")
@click.option("-e", "--exclude", help="Exclude matches with these tags or names.")
@click.option("-o", "--only-text", is_flag=True, help="Do not scan files or folders.")
@click.option("-k", "--key", help="Sort by the specified key.")
@click.option("--reverse", is_flag=True, help="Sort in reverse order.")
@click.option(
    "--top",
    metavar="N",
    help="Only show the N most likely matches, or N% of them, e.g. --top 10 or --top 5%.",
)
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
    help="Disable the processing of matches, e.g. adding dates to Unix timestamps or checking the checksums of Bitcoin addresses.",
)
@click.option(
    "--verify",
    is_flag=True,
    help="Ask the services if the keys found are valid, e.g. Google API keys. This sends the keys to the services.",
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
@click.option(
    "--stream",
    is_flag=True,
    help="Print every match as soon as it is found, not once the search is complete.",
)
@click.option(
    "--no-progress",
    is_flag=True,
    help="Do not show progress bars while searching.",
)
def main(**kwargs):
    """
    pyWhat - Identify what something is.

    Made by Bee https://twitter.com/bee_sec_san

    https://github.com/bee-san

    Filtration:

        --rarity min:max

            Rarity is how unlikely something is to be a false-positive. The higher the number, the more unlikely.

            Only print entries with rarity in range [min,max]. min and max can be omitted.

            Note: PyWhat by default has a rarity of 0.1. To see all matches, with many potential false positives use `0:`. For example, a YouTube video ID on its own, such as 'dQw4w9WgXcQ', is only shown with `--rarity 0:`.

        --include list

            Only include entries containing at least one tag in a list. List is a comma separated list.

        --exclude list

            Exclude specified tags. List is a comma separated list.

        The names of the regexes work like tags. Many regexes have alternative names too, such as 'ETH Wallet' for 'Ethereum (ETH) Wallet Address', so --include 'BTC Wallet,ETH Wallet' only shows Bitcoin and Ethereum wallets.

        --names

            Show the name of every regex, followed by its alternative names.

    Sorting:

        --key key_name

            Sort by the given key.

        --reverse

            Sort in reverse order.

        Available keys:

            name - Sort by the name of regex pattern

            rarity - Sort by rarity

            matched - Sort by a matched string

            likely - Sort the most likely matches first, see Top matches

            none - No sorting is done (the default)

    Top matches:

        --top N

            Only show the N most likely matches, e.g. --top 10. --top N% shows the most likely N percent of them, e.g. --top 5%. For a directory or several inputs, these are the most likely matches of all of them.

            The most likely matches are shown first, unless --key sorts them. They have the highest rarity, but fragments of a longer word or match, which boundaryless mode finds, are less likely unless their rarity is 1. For example, the card and social security numbers in '0x52908400098527886E0F7030069857D2E4169EE7' are fragments of the Ethereum address, which is the most likely match.

            How many matches were left out is shown on stderr. Use --interactive to page through all of them.

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

        Bitcoin wallet addresses whose checksum is wrong, like 3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F, are filtered out.

        '--disable-processing' flag can be used to show the matches as the regexes found them.

    Verification:

        --verify

            Ask the services if the keys that are found are valid, and add the answer to the description, e.g. 'Verification: invalid, Google rejected the key (API_KEY_INVALID)'. Currently Google API keys are verified: pywhat --verify 'AIzaSyA00000000000000000000000000000000'

            Only use it for keys that you are allowed to test: it sends the keys to the services (over HTTPS), once per key. It works with '--disable-processing' too.

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

            With --top N or the 'top N' command, searches show the N most likely matches and the 'more' command the next N.

    Progress and streaming:

        When a search takes a while, progress bars show how far it is: one for the regexes that are searched for in a file, with the regex that is searched for now, and one for the files of a directory or of several inputs. They are only shown on a terminal (on stderr if the output is redirected to a file), and they are removed once the search is complete.

        --no-progress

            Do not show the progress bars.

        --stream

            Print every match as soon as it is found, instead of once the search is complete. With --json, every match is a JSON object of its own, on one line, without the "Fragment" key, as whether a match is a fragment is only known once its file has been searched. --stream cannot sort the matches (--key), show only the most likely ones (--top) or print a table (--format pretty), as these need all the matches.

    Unicode:

        Files and text piped to pyWhat can be UTF-8, or UTF-16 or UTF-32 with a byte order mark (BOM). The UTF-16 strings in binary files, which 'strings -el' shows, are searched too.

        Characters that the terminal cannot show are printed as escape sequences such as '\\u20bf'.

    Examples:

        * what 'HTB{this is a flag}'

        * what '0x52908400098527886E0F7030069857D2E4169EE7'

        * what -- '52.6169586, -1.9779857'

        * what --rarity 0.6: 'myEmail@host.org'

        * what --rarity 0: --include "credentials" --exclude "aws" 'James:SecretPassword'

        * what -br 0.6: -be URL '123myEmail@host.org456'

        * what --top 1 '0x52908400098527886E0F7030069857D2E4169EE7'

    Your text must either be in quotation marks, or use the POSIX standard of "--" to mean "anything after -- is textual input".


    pyWhat can also search files or even a whole directory with recursion:

        * what 'secret.txt'

        * what 'this/is/a/path'

        * what --interactive 'this/is/a/path'

        * what --stream 'big.log'

    Several inputs, files, directories or text, can be searched at once. Then the file of every match is shown, and the matches in text are under "text":

        * what 'secret.txt' 'this/is/a/path' 'HTB{this is a flag}'

        * find . -name '*.log' -exec what {} +

    Text with spaces needs quotation marks, as every argument is an input.

    """
    # Print the characters that the terminal cannot show as escape sequences
    # instead of crashing, e.g. the Bitcoin sign (U+20BF) on Windows
    escape_unencodable(sys.stdout)
    if not kwargs["text_input"] and not kwargs["interactive"]:
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
    processors: Optional[List[Processor]] = [] if kwargs["disable_processing"] else None
    if kwargs["verify"]:
        # Verification is asked for, so --disable-processing keeps it
        processors = (
            [] if kwargs["disable_processing"] else default_processors()
        ) + verifiers()
    what_obj = What_Object(dist, processors)
    if kwargs["key"] is None:
        key = Keys.NONE
    else:
        try:
            key = str_to_key(kwargs["key"])
        except ValueError:
            print("Invalid key")
            sys.exit(1)
    top = None
    if kwargs["top"] is not None:
        try:
            top = parse_top(kwargs["top"])
        except ValueError as error:
            print(error)
            sys.exit(1)
    json_output = kwargs["json"] or str(kwargs["format"]).strip() == "json"
    if kwargs["stream"]:
        # The matches are printed as soon as they are found (issue #189)
        if key != Keys.NONE:
            sys.exit(
                "--stream cannot sort the matches, so it cannot be used with --key"
            )
        if not json_output and str(kwargs["format"]).strip() == "pretty":
            sys.exit(
                "--stream cannot print a table, so it cannot be used with --format pretty"
            )
        if top is not None:
            sys.exit(
                "--stream cannot pick the most likely matches, so it cannot be used "
                "with --top"
            )
        if kwargs["interactive"]:
            sys.exit("--stream cannot be used with --interactive")
    if kwargs["interactive"]:
        InteractiveShell(
            query_from_options(kwargs["rarity"], kwargs["include"], kwargs["exclude"]),
            boundaryless=boundaryless,
            only_text=kwargs["only_text"],
            include_filenames=kwargs["include_filenames"],
            processors=processors,
            key=key,
            reverse=kwargs["reverse"],
            top=top,
            json_output=kwargs["json"],
            format_str=kwargs["format"],
            print_tags=kwargs["print_tags"],
            progress=not kwargs["no_progress"],
        ).run(kwargs["text_input"] or None)
        return

    p = printer.Printing()
    # Progress bars on the terminal while searching (issue #189), on stderr if
    # the output is redirected
    with progress_bars(
        p.console, enabled=not kwargs["no_progress"], stderr=True
    ) as progress:
        if kwargs["stream"]:
            p.print_stream(
                what_obj.iter_what_is_this(
                    kwargs["text_input"],
                    kwargs["only_text"],
                    boundaryless,
                    kwargs["include_filenames"],
                    progress=progress,
                ),
                kwargs["text_input"],
                kwargs["print_tags"],
                format_str=None if json_output else kwargs["format"],
                json_output=json_output,
            )
            return
        identified_output = what_obj.what_is_this(
            kwargs["text_input"],
            kwargs["only_text"],
            key if top is None else Keys.NONE,  # top_matches() sorts the top ones
            kwargs["reverse"],
            boundaryless,
            kwargs["include_filenames"],
            progress=progress,
        )
    total = len(located_matches(identified_output))
    if top is not None:
        identified_output = top_matches(
            identified_output, top, key=key, reverse=kwargs["reverse"]
        )

    if json_output:
        p.print_json(identified_output)
    elif str(kwargs["format"]).strip() == "pretty":
        p.pretty_print(identified_output, kwargs["text_input"], kwargs["print_tags"])
    elif kwargs["format"] is not None:
        p.format_print(identified_output, kwargs["format"])
    else:
        p.print_raw(identified_output, kwargs["text_input"], kwargs["print_tags"])

    print_left_out(len(located_matches(identified_output)), total)


class What_Object:
    def __init__(self, distribution, processors=None):
        self.id = identifier.Identifier(dist=distribution, processors=processors)

    def what_is_this(
        self,
        text: Union[str, Sequence[str]],
        only_text: bool,
        key,
        reverse: bool,
        boundaryless: Filter,
        include_filenames: bool,
        progress: Optional[Callable[[Progress], Any]] = None,
    ) -> dict:
        """
        Returns a Python dictionary of everything that has been identified in
        text, or in every input of a list or tuple of inputs (issue #171)
        """
        inputs = [text] if isinstance(text, str) else text
        return self.id.identify_inputs(
            inputs,
            only_text=only_text,
            key=key,
            reverse=reverse,
            boundaryless=boundaryless,
            include_filenames=include_filenames,
            progress=progress,
        )

    def iter_what_is_this(
        self,
        text: Union[str, Sequence[str]],
        only_text: bool,
        boundaryless: Filter,
        include_filenames: bool,
        progress: Optional[Callable[[Progress], Any]] = None,
    ) -> Iterator[Found]:
        """
        Yields everything that is identified as soon as it is found (issue
        #189), see Identifier.iter_identify()
        """
        return self.id.iter_identify(
            text,
            only_text=only_text,
            boundaryless=boundaryless,
            include_filenames=include_filenames,
            progress=progress,
        )


if __name__ == "__main__":
    main()
