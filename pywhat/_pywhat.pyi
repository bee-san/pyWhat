"""The Rust crate's regex engine (py/src/lib.rs)."""
from typing import List, Tuple, Union

class MatchError(RuntimeError):
    """fancy-regex gave up on a search: it backtracked more than 100,000,000 times."""

class Text:
    """A text, encoded once for finditer()."""

    def __init__(self, text: str) -> None: ...

def finditer(pattern: str, text: Union[str, Text]) -> List[Tuple[int, int]]:
    """
    The (start, end) character offsets of every match of pattern in text, in
    order, like re.finditer(pattern, text, re.MULTILINE).
    """
