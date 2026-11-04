from importlib.metadata import PackageNotFoundError, version

from pywhat.filter import Distribution, Filter
from pywhat.helper import AvailableTags, Keys
from pywhat.identifier import Identifier, Progress
from pywhat.processors import Processor

try:
    # The version of the wheel, which is the version in Cargo.toml
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover
    # A checkout that isn't installed
    __version__ = "unknown"

tags = AvailableTags().get_tags()
pywhat_tags = tags  # left for backward compatibility purposes

__all__ = [
    "Identifier",
    "Distribution",
    "tags",
    "pywhat_tags",
    "Keys",
    "Filter",
    "Processor",
    "Progress",
]


del AvailableTags, filter, PackageNotFoundError, version


def __dir__():
    return __all__ + ["__version__"]
