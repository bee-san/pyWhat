"""
Interactive mode (pywhat --interactive), see issue #233.

The input is identified once, with every regex, and the matches are kept in
memory. They can then be searched as often as needed without scanning the
input again, with searches such as

    location:"/", include:"Bug Bounty", exclude:"Credit Card", rarity:"0.1:0.6"
"""
import cmd
import glob
import inspect
import json
import os
import re
import string
from collections import Counter
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Tuple,
    Union,
)

from rich.columns import Columns
from rich.console import Console
from rich.markup import escape

from pywhat.filter import Distribution, Filter
from pywhat.helper import AvailableTags, CaseInsensitiveSet, Keys
from pywhat.identifier import Identifier
from pywhat.printer import Printing

# Search keys, including the "includes" and "excludes" spelling of #233
_SEARCH_KEYS = {
    "location": "location",
    "include": "include",
    "includes": "include",
    "exclude": "exclude",
    "excludes": "exclude",
    "rarity": "rarity",
}
_KEY_NAMES = ["location", "include", "exclude", "rarity"]
# The order of the parts of a search when it is shown, free text ("") first
_ORDER = [""] + _KEY_NAMES

# The defaults of Filter and the --rarity option
MIN_RARITY = 0.1
MAX_RARITY = 1

# key:value, key:"quoted value", "quoted text" or text. Unknown keys are
# text, so that searching for http://example.com works. Unquoted values can
# be lists of tags (include:AWS,Google), commas separate everything else.
_TOKEN = re.compile(
    r'(?P<key>[A-Za-z]+):(?:"(?P<quoted_value>[^"]*)(?P<value_end>"?)|(?P<value>[^\s"]*))'
    r'|"(?P<quoted_word>[^"]*)(?P<word_end>"?)'
    r'|(?P<word>[^\s",]+)'
)
# A line that starts with key: is a search, even if the key is a command
_SEARCH_LINE = re.compile(r"\s*[A-Za-z]+:")

INTRO = (
    "[bold #D7Afff]pyWhat interactive mode[/bold #D7Afff]. Type 'help' for the "
    "commands, 'help search' for the search syntax and 'quit' to leave."
)
NOTHING_LOADED = "Nothing is loaded yet, use 'load FILE, DIRECTORY or TEXT'."


class QueryError(ValueError):
    """Raised for a search that cannot be understood."""


class _Token(NamedTuple):
    key: str  # search key, "" for free text
    value: str
    start: int
    end: int
    value_start: int  # after the opening quote, if there is one
    quoted: bool
    closed: bool  # whether the closing quote has been typed


def _scan(query: str) -> Iterator[_Token]:
    """Split a search into its parts, which are separated by spaces or commas."""
    for match in _TOKEN.finditer(query):
        key = _SEARCH_KEYS.get((match.group("key") or "").lower(), "")
        group: Union[int, str] = 0  # text, possibly looking like key:value
        if key:
            group = "value" if match.group("quoted_value") is None else "quoted_value"
        elif match.group("quoted_word") is not None:
            group = "quoted_word"
        quoted = group in ("quoted_value", "quoted_word")
        value = match.group(group)
        if group == 0:
            # e.g. incldue:"Bug Bounty", the quotes cannot be shown in "text"
            value = value.replace('"', "")
        yield _Token(
            key,
            value.strip() if quoted else value.strip(string.whitespace + ","),
            match.start(),
            match.end(),
            match.start(group),
            quoted,
            bool(match.group("value_end") or match.group("word_end")),
        )


def parse_rarity(rarity: str) -> Tuple[float, float]:
    """
    Parse a rarity range such as "0.1:0.6" or "0.1 - 0.6". Like with --rarity,
    a bound can be left out ("0.5:" or ":0.5"). A single rarity, such as "0.5",
    is the range from that rarity to the same rarity.
    """
    bounds = rarity.split(":") if ":" in rarity else re.split(r"(?<=\d)\s*-", rarity)
    if len(bounds) == 1:
        bounds *= 2
    try:
        if not rarity.strip() or len(bounds) != 2:
            raise ValueError
        min_rarity = float(bounds[0]) if bounds[0].strip() else MIN_RARITY
        max_rarity = float(bounds[1]) if bounds[1].strip() else MAX_RARITY
    except ValueError:
        raise QueryError(
            f"Invalid rarity '{rarity}', use a range such as 0.1:0.6 or 0.5: "
            "or a single rarity such as 0.5"
        ) from None
    return min_rarity, max_rarity


def _normalise_location(location: str) -> str:
    return location.replace("\\", "/").lower()


class Query:
    """
    A search through the loaded matches, for example
    'location:"/", include:"Bug Bounty", exclude:"Credit Card", rarity:"0.1:0.6"'.

    Every part of a search has to match:

    * location:PATH - the location of the match (the file) contains PATH
    * include:TAG[,TAG...] - the match has at least one of the tags
    * exclude:TAG[,TAG...] - the match has none of the tags
    * rarity:MIN:MAX - the rarity is in the range, see parse_rarity().
      A search without a rarity uses 0.1:1, like the --rarity option.
    * anything else is text that the matched text or the name contains
    """

    def __init__(self, query: str = ""):
        self.parts: List[Tuple[str, str]] = []
        self._filters: List[Filter] = []
        self._locations: List[str] = []
        self._words: List[str] = []
        for token in _scan(query):
            self._add(token.key, token.value)
        if not any(key == "rarity" for key, _ in self.parts):
            self._add("rarity", f"{MIN_RARITY}:{MAX_RARITY}")

    def _add(self, key: str, value: str) -> None:
        if not value:
            if key:
                raise QueryError(f'{key}: needs a value, e.g. {key}:"..."')
            return
        if key == "rarity":
            min_rarity, max_rarity = parse_rarity(value)
            self._filters.append(
                Filter({"MinRarity": min_rarity, "MaxRarity": max_rarity})
            )
            value = f"{min_rarity:g}"
            if min_rarity != max_rarity:
                value += f":{max_rarity:g}"
        elif key in ("include", "exclude"):
            tags = [tag.strip() for tag in value.split(",") if tag.strip()]
            if not tags:
                raise QueryError(f'{key}: needs a tag, e.g. {key}:"Bug Bounty"')
            available = CaseInsensitiveSet(AvailableTags().get_tags())
            for tag in tags:
                if tag not in available:
                    raise QueryError(
                        f"Unknown tag '{tag}'. Press Tab to complete tags, or run "
                        "'pywhat --tags' to see all of them."
                    )
            option = "Tags" if key == "include" else "ExcludeTags"
            self._filters.append(Filter({option: tags, "MinRarity": 0}))
            value = ",".join(tags)
        elif key == "location":
            self._locations.append(_normalise_location(value))
        else:
            self._words.append(value.lower())
        self.parts.append((key, value))

    def matches(self, location: str, match: dict) -> bool:
        """
        Whether the search finds a match, which is an item of a list in the
        "Regexes" of Identifier.identify(), found in location.
        """
        regex = match["Regex Pattern"]
        texts = (match["Matched"].lower(), regex["Name"].lower())
        return (
            all(regex in search_filter for search_filter in self._filters)
            and self.matches_location(location)
            and all(any(word in text for text in texts) for word in self._words)
        )

    def matches_location(self, location: str) -> bool:
        location = _normalise_location(location)
        return all(part in location for part in self._locations)

    def __str__(self) -> str:
        parts = sorted(self.parts, key=lambda part: _ORDER.index(part[0]))
        return ", ".join(
            f'{key}:"{value}"' if key else f'"{value}"' for key, value in parts
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self)!r})"


def query_from_options(
    rarity: Optional[str], include: Optional[str], exclude: Optional[str]
) -> str:
    """The search for the --rarity, --include and --exclude options."""
    options = (("include", include), ("exclude", exclude), ("rarity", rarity))
    return ", ".join(f'{key}:"{value}"' for key, value in options if value is not None)


def complete_query(
    before: str,
    tags: Iterable[str] = (),
    rarities: Iterable[float] = (),
    locations: Iterable[str] = (),
) -> Tuple[int, List[str]]:
    """
    Complete a search, before is the search up to the cursor. Returns where
    the completed text starts in before and the completions, which replace
    the text from there.

    Search keys are completed, and the values of include: and exclude: (from
    tags), rarity: (from rarities) and location: (from locations). Values are
    completed with quotes, so that include:Bug becomes include:"Bug Bounty".
    """
    tokens = list(_scan(before))
    keys = [key + ":" for key in _KEY_NAMES]
    if not tokens or tokens[-1].end < len(before):
        # After a separator, a new part of the search starts
        return len(before), keys
    token = tokens[-1]
    if not token.key:
        if token.quoted:
            return len(before), []
        word = before[token.start :].lower()
        return token.start, [key for key in keys if key.startswith(word)]
    if token.closed:
        return len(before), []

    if token.key == "rarity":
        values = [f"{rarity:g}" for rarity in sorted(set(rarities))]
    elif token.key == "location":
        values = sorted(set(locations))
    else:
        values = sorted(set(tags), key=str.lower)
    typed = before[token.value_start :]
    # The tags before the one that is completed, "AWS," in include:"AWS,Bug
    done = ""
    if token.key in ("include", "exclude"):
        done = typed[: typed.rfind(",") + 1]
        rest = typed[len(done) :]
        done += rest[: len(rest) - len(rest.lstrip())]
        typed = typed[len(done) :]
    found = [value for value in values if value.lower().startswith(typed.lower())]
    if token.quoted:
        return token.value_start + len(done), [value + '"' for value in found]
    return token.value_start, ['"' + done + value + '"' for value in found]


def _readline_matches(
    line: str, begidx: int, start: int, completions: Iterable[str]
) -> List[str]:
    """
    readline replaces line[begidx:] (up to the cursor) with the match that is
    chosen. Turn completions of line[start:] into such matches.
    """
    if begidx <= start:
        return [line[begidx:start] + completion for completion in completions]
    typed = line[start:begidx].lower()
    return [
        completion[len(typed) :]
        for completion in completions
        if completion.lower().startswith(typed)
    ]


def _argument_start(line: str) -> int:
    """Where the argument starts in a command line such as 'load file'."""
    words = line.split(None, 1)
    rest = line[len(words[0]) :] if words else ""
    return len(line) - len(rest.lstrip())


def _count_matches(number: int) -> str:
    return f"{number} match" + ("" if number == 1 else "es")


def _readline() -> Any:
    """The readline module, None where there is none (e.g. on Windows)."""
    try:
        import readline
    except ImportError:
        return None
    return readline


class InteractiveShell(cmd.Cmd):
    """
    pyWhat's interactive mode: load input into memory, then search through
    the matches. Run it with run().

    The options are the ones of the command line interface: query is the
    search to start with (see Query). boundaryless (by default the one of
    the command line, Filter()), only_text and include_filenames are used to
    identify the loaded input. key, reverse, json_output, format_str and
    print_tags format the matches.
    """

    prompt = "pywhat> "

    def __init__(
        self,
        query: str = "",
        *,
        boundaryless: Optional[Filter] = None,
        only_text: bool = False,
        include_filenames: bool = False,
        key: Any = Keys.NONE,
        reverse: bool = False,
        json_output: bool = False,
        format_str: Optional[str] = None,
        print_tags: bool = False,
        console: Optional[Console] = None,
        stdin: Any = None,
        stdout: Any = None,
    ):
        super().__init__(stdin=stdin, stdout=stdout)
        if stdin is not None:
            self.use_rawinput = False  # read the commands from stdin
        self.console = (
            Console(highlight=False, file=stdout) if console is None else console
        )
        self.initial_query = self.query = Query(query)
        # Identify with every regex, the search filters the matches
        self._identifier = Identifier(
            dist=Distribution(Filter({"MinRarity": 0})),
            boundaryless=Filter() if boundaryless is None else boundaryless,
        )
        self.only_text = only_text
        self.include_filenames = include_filenames
        self.key = key
        self.reverse = reverse
        self.json_output = json_output
        self.format_str = format_str
        self.print_tags = print_tags
        self.input: Optional[str] = None
        self.matches: List[Tuple[str, dict]] = []  # (location, match)
        self.signatures: Dict[str, dict] = {}

    def run(self, text_input: Optional[str] = None) -> None:
        """Load text_input, if given, then read commands until 'quit'."""
        self.console.print(INTRO)
        if text_input is None:
            self.console.print(NOTHING_LOADED)
        else:
            self.load(text_input)
        self.cmdloop(intro="")

    def load(self, text: str) -> None:
        """Identify everything in a file, directory or text and keep it in memory."""
        try:
            with self.console.status("Loading..."):
                identified = self._identifier.identify(
                    text,
                    only_text=self.only_text,
                    include_filenames=self.include_filenames,
                )
        except OSError as error:
            self._error(f"Could not load '{text}': {error}")
            return
        self.input = text
        self.signatures = identified["File Signatures"] or {}
        self.matches = [
            (location, match)
            for location, matches in (identified["Regexes"] or {}).items()
            for match in matches
        ]
        source = "the text"
        if not self.only_text and os.path.isdir(text):
            source = f"directory '{text}'"
        elif not self.only_text and os.path.isfile(text):
            source = f"file '{text}'"
        self.console.print(
            f"Loaded {_count_matches(len(self.matches))} from {escape(source)}."
        )
        self.do_tags("")

    def search(self) -> List[Tuple[str, dict]]:
        """The loaded (location, match) pairs that the current search finds."""
        return [
            (location, match)
            for location, match in self.matches
            if self.query.matches(location, match)
        ]

    def show_matches(self) -> None:
        """Print the matches of the current search, like pywhat does."""
        found = self.search()
        self._print_search(found)
        regexes: Dict[str, List[dict]] = {}
        for location, match in found:
            regexes.setdefault(location, []).append(match)
        if self.key != Keys.NONE:
            for matches in regexes.values():
                matches.sort(key=self.key, reverse=self.reverse)
        identified = {
            "File Signatures": {
                location: signature
                for location, signature in self.signatures.items()
                if self.query.matches_location(location)
            }
            or None,
            "Regexes": regexes or None,
        }

        if self.json_output or str(self.format_str).strip() == "json":
            # Like Printing.print_json(), but to the stdout of the shell
            self.stdout.write(json.dumps(identified) + "\n")
            return
        printer = Printing()
        printer.console = self.console
        if str(self.format_str).strip() == "pretty":
            printer.pretty_print(identified, self.input, self.print_tags)
        elif self.format_str is not None:
            printer.format_print(identified, self.format_str)
        else:
            printer.print_raw(identified, self.input, self.print_tags)

    def _print_search(self, found: list) -> None:
        self.console.print(
            f"[bold #D7Afff]Search:[/bold #D7Afff] {escape(str(self.query))} "
            f"({len(found)} of {_count_matches(len(self.matches))})",
            soft_wrap=True,
        )

    def _error(self, message: str) -> None:
        self.console.print(f"[bold red]{escape(message)}[/bold red]")

    def _loaded(self) -> bool:
        if self.input is None:
            self.console.print(NOTHING_LOADED)
        return self.input is not None

    def _tags(self) -> List[str]:
        """The tags of the loaded matches, all tags if there are none."""
        tags = {
            tag for _, match in self.matches for tag in match["Regex Pattern"]["Tags"]
        }
        return sorted(tags or AvailableTags().get_tags(), key=str.lower)

    def _add_to_search(self, key: str, tags: str) -> None:
        tags = tags.replace('"', "").strip()  # include "Bug Bounty" works too
        if not tags:
            self._error(f"Which tags? Use '{key} TAG[,TAG...]'.")
            return
        self.do_search(f'{self.query}, {key}:"{tags}"')

    # Commands. Their docstrings are the help of the 'help' command.

    def do_load(self, arg: str) -> None:
        """
        load FILE, DIRECTORY or TEXT

        Identify everything in the input and keep the matches in memory, to
        search through them without scanning the input again. Replaces what
        was loaded before.
        """
        if not arg.strip():
            self._error("What should be loaded? Use 'load FILE, DIRECTORY or TEXT'.")
            return
        self.load(arg.strip())

    def do_search(self, arg: str) -> None:
        """
        search [SEARCH]

        Show the loaded matches that the search finds. A line that is not a
        command is a search too, and 'search' alone shows the current search
        again. Every part of a search has to match:

            location:PATH       the path of the file contains PATH
            include:TAG[,TAG]   the match has at least one of the tags
            exclude:TAG[,TAG]   the match has none of the tags
            rarity:MIN:MAX      the rarity is in the range (0.1:1 by default).
                                0.1 - 0.6, 0.5: and :0.5 work too, and a single
                                number such as 0.5 is that exact rarity.
            TEXT                the matched text or the name contains TEXT

        Values with spaces need quotes, parts can be separated with commas:

            location:"/", include:"Bug Bounty", exclude:"Credit Card", rarity:"0.1:0.6"

        Press Tab to complete search keys, tags, rarities and locations.
        """
        if arg.strip():
            try:
                self.query = Query(arg)
            except QueryError as error:
                self._error(str(error))
                return
        if self._loaded():
            self.show_matches()

    def do_include(self, arg: str) -> None:
        """
        include TAG[,TAG...]

        Narrow the current search down to the matches with at least one of
        the tags, by adding include:"TAG[,TAG...]" to it.
        """
        self._add_to_search("include", arg)

    def do_exclude(self, arg: str) -> None:
        """
        exclude TAG[,TAG...]

        Remove the matches with any of the tags from the current search, by
        adding exclude:"TAG[,TAG...]" to it.
        """
        self._add_to_search("exclude", arg)

    def do_tags(self, arg: str) -> None:
        """
        tags

        Show the tags of the matches that the current search finds, with the
        number of matches for each tag. Use 'include TAG' or 'exclude TAG' to
        narrow the search down.
        """
        if not self._loaded():
            return
        found = self.search()
        self._print_search(found)
        counts = Counter(
            tag for _, match in found for tag in match["Regex Pattern"]["Tags"]
        )
        if not counts:
            self.console.print("Nothing found!")
            return
        tags = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
        self.console.print(
            Columns(
                [f"{escape(tag)} [dim]({count})[/dim]" for tag, count in tags],
                padding=(0, 3),
                column_first=True,
            )
        )

    def do_clear(self, arg: str) -> None:
        """
        clear

        Go back to the search that pyWhat started with (the one of the
        --rarity, --include and --exclude options) and show its matches.
        """
        self.query = self.initial_query
        if self._loaded():
            self.show_matches()

    def do_quit(self, arg: str) -> bool:
        """
        quit

        Leave interactive mode. 'exit' and Ctrl+D work too.
        """
        return True

    do_exit = do_quit

    def do_EOF(self, arg: str) -> bool:
        self.console.print()
        return True

    def do_help(self, arg: str) -> Optional[bool]:
        """
        help [COMMAND]

        Show the commands, or the help of a command.
        """
        method = getattr(self, "do_" + arg.strip(), None) if arg.strip() else None
        if method is not None and method.__doc__:
            self.stdout.write(inspect.cleandoc(method.__doc__) + "\n")
            return None
        return super().do_help(arg)

    # The behaviour of cmd.Cmd that is changed

    def parseline(self, line: str) -> Tuple[Optional[str], Optional[str], str]:
        # include:"Bug Bounty" is a search, not the include command
        if _SEARCH_LINE.match(line):
            line = line.strip()
            return "search", line, line
        return super().parseline(line)

    def default(self, line: str) -> bool:
        # A line that is not a command is a search
        self.do_search(line)
        return False

    def emptyline(self) -> bool:
        # Do not repeat the last command
        return False

    def get_names(self) -> List[str]:
        # EOF (Ctrl+D) is not a command to show in the help
        return [name for name in super().get_names() if name != "do_EOF"]

    def cmdloop(self, intro: Optional[Any] = None) -> None:
        readline = _readline() if self.use_rawinput and self.completekey else None
        if readline is not None:
            delims = readline.get_completer_delims()
            # Only whitespace separates the words that are completed, so that
            # search parts such as include:"Bug Bounty" are completed as a whole
            readline.set_completer_delims(" \t\n")
        try:
            while True:
                try:
                    super().cmdloop(intro)
                    return
                except KeyboardInterrupt:
                    # Ctrl+C cancels the line or the command (e.g. a long
                    # load), it does not leave interactive mode
                    self.console.print()
                    intro = ""
        finally:
            if readline is not None:
                readline.set_completer_delims(delims)

    # Tab completion

    def _complete_search(
        self, line: str, query_start: int, begidx: int, endidx: int
    ) -> List[str]:
        start, completions = complete_query(
            line[query_start:endidx],
            tags=self._tags(),
            rarities={match["Regex Pattern"]["Rarity"] for _, match in self.matches},
            locations={location for location, _ in self.matches},
        )
        return _readline_matches(line, begidx, query_start + start, completions)

    def completenames(self, text: str, *ignored: Any) -> List[str]:
        # The first word is a command or the start of a search
        commands = super().completenames(text, *ignored)
        return commands + self._complete_search(text, 0, 0, len(text))

    def complete_help(self, *args: Any) -> List[str]:
        return [name for name in super().complete_help(*args) if ":" not in name]

    def completedefault(self, *ignored: Any) -> List[str]:
        # A search that does not start with a search key, e.g. 'bitcoin rar'
        text, line, begidx, endidx = ignored
        command = self.parseline(line)[0]
        if command and hasattr(self, "do_" + command):
            return []  # tags, clear and quit have no arguments
        return self._complete_search(line, 0, begidx, endidx)

    def complete_search(
        self, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        # parseline() sends searches such as 'include:"Bug' here too
        query_start = 0 if _SEARCH_LINE.match(line) else _argument_start(line)
        return self._complete_search(line, query_start, begidx, endidx)

    def complete_include(
        self, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        typed = line[:endidx]
        start = max(_argument_start(typed), typed.rfind(",") + 1)
        start += len(typed[start:]) - len(typed[start:].lstrip())
        found = [
            tag for tag in self._tags() if tag.lower().startswith(typed[start:].lower())
        ]
        return _readline_matches(line, begidx, start, found)

    complete_exclude = complete_include

    def complete_load(
        self, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        start = _argument_start(line[:endidx])
        paths = glob.glob(glob.escape(line[start:endidx]) + "*")
        found = sorted(path + os.sep if os.path.isdir(path) else path for path in paths)
        return _readline_matches(line, begidx, start, found)
