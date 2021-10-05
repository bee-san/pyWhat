from pywhat.filter import Distribution, Filter
from pywhat.helper import AvailableTags, Keys
from pywhat.identifier import Identifier

__version__ = "4.1.0"

tags = AvailableTags().get_tags()
pywhat_tags = tags  # left for backward compatibility purposes

_contents = ["Identifier", "Distribution", "tags", "pywhat_tags", "Keys", "Filter"]


__all__ = _contents

del AvailableTags, filter


def __dir__():
    return _contents + ["__version__"]
