#! /usr/bin/env python3

"""
pyWhat: Identify Anything.
"""

import platform
import sys

if __name__ == "__main__":
    if sys.version_info < (3, 6):
        print(
            f"What requires Python 3.6+, you are using {platform.python_version()}. Please install a higher Python version."
        )
        sys.exit(1)

    from pywhat import what

    if len(sys.argv) == 1:
        what.main(["--help"])

    what.main()
