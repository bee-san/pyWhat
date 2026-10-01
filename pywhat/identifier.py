import glob
import os.path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Tuple,
    Union,
)

import pywhat.magic_numbers
from pywhat.filter import Distribution, Filter
from pywhat.helper import Keys
from pywhat.processors import Processor
from pywhat.regex_identifier import RegexIdentifier
from pywhat.unicode import read_file


class Progress(NamedTuple):
    """
    How far a search is (issue #189). The progress callback of
    Identifier.identify(), identify_inputs() and iter_identify() is called
    with a Progress before every regex is searched for, and when a file has
    been searched.

    The files (a text is one "file" too) are searched one after another.
    Every regex is searched for in every text of a file: in its contents, in
    the UTF-16 strings in it and, with include_filenames, in its name.
    """

    # The file that is searched, or "text", like the keys of identify()
    location: str
    # How many files have been searched, of how many files
    files_done: int
    files: int
    # How many of the regex searches of the file are done, of how many: the
    # number of regexes times the number of texts in the file (usually one)
    regexes_done: int
    regexes: int
    # The name of the regex that is searched for now, None once the file has
    # been searched
    regex: Optional[str]


# What iter_identify() yields: (kind, location, value)
Found = Tuple[str, str, dict]


def _regex_progress(
    progress: Callable[[Progress], Any],
    location: str,
    files_done: int,
    files: int,
    regexes: int,
) -> Callable[[str], None]:
    """The progress callback of RegexIdentifier.iter_check() for a file."""
    regexes_done = 0

    def report(regex: str) -> None:
        nonlocal regexes_done
        progress(Progress(location, files_done, files, regexes_done, regexes, regex))
        regexes_done += 1

    return report


class Identifier:
    def __init__(
        self,
        *,
        dist: Optional[Distribution] = None,
        key=Keys.NONE,
        reverse=False,
        boundaryless: Optional[Filter] = None,
        processors: Optional[Iterable[Processor]] = None,
    ):
        self.distribution = Distribution() if dist is None else dist
        self.boundaryless = (
            Filter({"Tags": []}) if boundaryless is None else boundaryless
        )
        # processors=None uses pywhat.processors.default_processors()
        self._regex_id = RegexIdentifier(processors)
        self._key = key
        self._reverse = reverse

    def identify(
        self,
        text: str,
        *,
        only_text=True,
        dist: Distribution = None,
        key: Optional[Callable] = None,
        reverse: Optional[bool] = None,
        boundaryless: Optional[Filter] = None,
        include_filenames=False,
        processors: Optional[Iterable[Processor]] = None,
        progress: Optional[Callable[[Progress], Any]] = None,
    ) -> dict:
        """
        Identify everything in text, or in the file or the directory (which
        is searched recursively) at the path text, unless only_text is set.

        progress, if given, is called with a Progress while the search goes
        on, see Progress. iter_identify() yields the matches one at a time,
        as soon as they are found.
        """
        return self._collect(
            self.iter_identify(
                [text],
                only_text=only_text,
                dist=dist,
                boundaryless=boundaryless,
                include_filenames=include_filenames,
                processors=processors,
                progress=progress,
            ),
            key,
            reverse,
        )

    def identify_inputs(
        self,
        inputs: Iterable[str],
        *,
        only_text=True,
        dist: Optional[Distribution] = None,
        key: Optional[Callable] = None,
        reverse: Optional[bool] = None,
        boundaryless: Optional[Filter] = None,
        include_filenames=False,
        processors: Optional[Iterable[Processor]] = None,
        progress: Optional[Callable[[Progress], Any]] = None,
    ) -> dict:
        """
        Identify several inputs at once (issue #171). Every input is a file, a
        directory or text, like the text of identify(), which has the same
        options.

        For a single input, this returns what identify() returns. For several
        inputs, it returns what was found in all of them, in the same format
        as for a directory: the matches and the file signatures of a file are
        under the path of the file, which is the input or, for the files of a
        directory, the path of the directory joined with the path of the file
        in it, e.g. "fixtures/test/file". The matches in text are under "text".
        """
        texts = list(inputs)
        options: Dict[str, Any] = dict(
            only_text=only_text,
            dist=dist,
            boundaryless=boundaryless,
            include_filenames=include_filenames,
            processors=processors,
            progress=progress,
        )
        if len(texts) == 1:
            return self.identify(texts[0], key=key, reverse=reverse, **options)
        return self._collect(self.iter_identify(texts, **options), key, reverse)

    def iter_identify(
        self,
        text: Union[str, Iterable[str]],
        *,
        only_text=True,
        dist: Optional[Distribution] = None,
        boundaryless: Optional[Filter] = None,
        include_filenames=False,
        processors: Optional[Iterable[Processor]] = None,
        progress: Optional[Callable[[Progress], Any]] = None,
    ) -> Iterator[Found]:
        """
        Like identify(), or identify_inputs() if text is a list of inputs, but
        a generator which yields everything as soon as it is found (issue
        #189), instead of returning it all once the search is complete:

        * ("File Signatures", location, file_signature) for a file with a
          file signature, before its matches
        * ("Regexes", location, match) for every match

        location is the file, or "text", and file_signature and match are
        what identify() returns under location in its "File Signatures" and
        "Regexes". identify() puts everything together, and sorts the matches.

        A match gets its "Fragment" key (see pywhat.ranking.mark_fragments())
        after it has been yielded, once every regex has been searched for in
        the text it was found in, as only then is it known.
        """
        if dist is None:
            dist = self.distribution
        if boundaryless is None:
            boundaryless = self.boundaryless
        if processors is None:
            processors = self._regex_id.processors
        else:
            processors = list(processors)  # used for every file
        inputs = [text] if isinstance(text, str) else list(text)

        files = self._files(inputs, only_text)
        for files_done, (location, source, is_file) in enumerate(files):
            if is_file:
                magic_numbers = pywhat.magic_numbers.get_magic_nums(source)
                if not magic_numbers:
                    magic_numbers = pywhat.magic_numbers.check_magic_nums(source)
                if magic_numbers:
                    yield "File Signatures", location, magic_numbers

                # UTF-8, UTF-16 or UTF-32 text, and the UTF-16LE strings in
                # binary files (issue #34)
                contents = read_file(source)
                if include_filenames:
                    contents.append(os.path.basename(source))
            else:
                contents = [source]

            regexes = len(dist.get_regexes()) * len(contents)
            on_regex = None
            if progress is not None:
                on_regex = _regex_progress(
                    progress, location, files_done, len(files), regexes
                )
            for match in self._regex_id.iter_check(
                contents,
                dist=dist,
                boundaryless=boundaryless,
                processors=processors,
                progress=on_regex,
            ):
                yield "Regexes", location, match
            if progress is not None:
                progress(
                    Progress(
                        location, files_done + 1, len(files), regexes, regexes, None
                    )
                )

    def _files(self, inputs: List[str], only_text: bool) -> List[Tuple[str, str, bool]]:
        """
        What there is to search in the inputs, (location, source, is_file):
        the path of every file (source) with its location, and every text
        (source) with the location "text".
        """
        several = len(inputs) != 1
        files = []
        for text in inputs:
            if not only_text and os.path.isdir(text):
                # if input is a directory, recursively search for all of the files
                directory = os.path.abspath(text)
                for myfile in glob.iglob(text + "/**", recursive=True):
                    if os.path.isfile(myfile):
                        path = os.path.abspath(myfile)
                        # The path of the file in the directory, e.g. "/test/file"
                        name = path.replace(directory, "")
                        if several:
                            # The path of the directory joined with it, e.g.
                            # "fixtures/test/file"
                            name = os.path.join(text, name.lstrip(os.sep))
                        files.append((name, path, True))
            elif not only_text and os.path.isfile(text):
                files.append((text if several else os.path.basename(text), text, True))
            else:
                files.append(("text", text, False))
        return files

    def _collect(
        self,
        found: Iterable[Found],
        key: Optional[Callable] = None,
        reverse: Optional[bool] = None,
    ) -> dict:
        """What identify() returns, from what iter_identify() yields."""
        if key is None:
            key = self._key
        if reverse is None:
            reverse = self._reverse

        identify_obj: dict = {"File Signatures": {}, "Regexes": {}}
        for kind, location, value in found:
            if kind == "Regexes":
                identify_obj["Regexes"].setdefault(location, []).append(value)
            else:
                identify_obj["File Signatures"][location] = value

        if key != Keys.NONE:
            # The matches of every file of a directory, not only the last one.
            # The matches of several texts are all under "text", and a file
            # can be given twice (or in a directory that is given too).
            for matches in identify_obj["Regexes"].values():
                matches.sort(key=key, reverse=reverse)

        for key_, value in identify_obj.items():
            # if there are zero regex or file signature matches, set it to None
            if not value:
                identify_obj[key_] = None

        return identify_obj
