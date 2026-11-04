"""
Validators (checksums) of the regexes in pywhat/Data/regexes/files.json.

Add a function that returns whether a match is valid, document what it checks and how many
random strings pass it, and name it in VALIDATORS. Use the Python standard library only.
src/validators/files.rs has the same validators in Rust, and they must agree.
"""
from typing import Callable, Dict

VALIDATORS: Dict[str, Callable[[str], bool]] = {}
