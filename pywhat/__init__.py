from pywhat.filter import Distribution, Filter
from pywhat.helper import AvailableTags, Keys
from pywhat.identifier import Identifier, Progress
from pywhat.processors import Processor

__version__ = "5.0.0"

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


del AvailableTags, filter


def __dir__():
    return __all__ + ["__version__"]
