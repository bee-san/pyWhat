import glob
import os.path
from typing import Any, Callable, Dict, Iterable, Optional

import pywhat.magic_numbers
from pywhat.filter import Distribution, Filter
from pywhat.helper import Keys
from pywhat.processors import Processor
from pywhat.regex_identifier import RegexIdentifier
from pywhat.unicode import read_file


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
    ) -> dict:
        if dist is None:
            dist = self.distribution
        if key is None:
            key = self._key
        if reverse is None:
            reverse = self._reverse
        if boundaryless is None:
            boundaryless = self.boundaryless
        if processors is None:
            processors = self._regex_id.processors
        else:
            processors = list(processors)  # used for every file of a directory

        identify_obj: dict = {"File Signatures": {}, "Regexes": {}}
        search = []

        if not only_text and os.path.isdir(text):
            # if input is a directory, recursively search for all of the files
            for myfile in glob.iglob(text + "/**", recursive=True):
                if os.path.isfile(myfile):
                    search.append(os.path.abspath(myfile))
        else:
            search = [text]

        for string in search:
            if not only_text and os.path.isfile(string):
                if os.path.isdir(text):
                    short_name = string.replace(os.path.abspath(text), "")
                else:
                    short_name = os.path.basename(string)

                magic_numbers = pywhat.magic_numbers.get_magic_nums(string)
                # UTF-8, UTF-16 or UTF-32 text, and the UTF-16LE strings in
                # binary files (issue #34)
                contents = read_file(string)

                if include_filenames:
                    contents.append(os.path.basename(string))

                regex = self._regex_id.check(
                    contents,
                    dist=dist,
                    boundaryless=boundaryless,
                    processors=processors,
                )

                if not magic_numbers:
                    magic_numbers = pywhat.magic_numbers.check_magic_nums(string)

                if magic_numbers:
                    identify_obj["File Signatures"][short_name] = magic_numbers
            else:
                short_name = "text"
                regex = self._regex_id.check(
                    search,
                    dist=dist,
                    boundaryless=boundaryless,
                    processors=processors,
                )

            if regex:
                identify_obj["Regexes"][short_name] = regex

        if key != Keys.NONE:
            # The matches of every file of a directory, not only the last one
            for matches in identify_obj["Regexes"].values():
                matches.sort(key=key, reverse=reverse)

        for key_, value in identify_obj.items():
            # if there are zero regex or file signature matches, set it to None
            if not value:
                identify_obj[key_] = None

        return identify_obj

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
        if key is None:
            key = self._key
        if reverse is None:
            reverse = self._reverse
        if processors is not None:
            processors = list(processors)  # used for every input
        options: Dict[str, Any] = dict(
            only_text=only_text,
            dist=dist,
            key=key,
            reverse=reverse,
            boundaryless=boundaryless,
            include_filenames=include_filenames,
            processors=processors,
        )
        if len(texts) == 1:
            return self.identify(texts[0], **options)

        identify_obj: dict = {"File Signatures": {}, "Regexes": {}}
        for text in texts:
            identified = self.identify(text, **options)
            is_directory = not only_text and os.path.isdir(text)
            is_file = not only_text and os.path.isfile(text)
            for kind, found in identified.items():
                for name, value in (found or {}).items():
                    if is_directory:
                        # name is the path of the file in the directory, e.g.
                        # "/test/file"
                        name = os.path.join(text, name.lstrip(os.sep))
                    elif is_file:
                        name = text  # instead of the name of the file
                    if kind == "Regexes":
                        identify_obj[kind].setdefault(name, []).extend(value)
                    else:
                        identify_obj[kind][name] = value

        if key != Keys.NONE:
            # The matches of several texts are all under "text", and a file can
            # be given twice (or in a directory that is given too)
            for matches in identify_obj["Regexes"].values():
                matches.sort(key=key, reverse=reverse)

        for key_, value in identify_obj.items():
            if not value:
                identify_obj[key_] = None

        return identify_obj
