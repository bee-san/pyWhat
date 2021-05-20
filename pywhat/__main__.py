#! /usr/bin/env python3

"""
pywhat: Identify Anything.
"""

import sys

if __name__ == "__main__":
    major = sys.version_info[0]
    minor = sys.version_info[1]

    python_version = (
        str(sys.version_info[0])
        + "."
        + str(sys.version_info[1])
        + "."
        + str(sys.version_info[2])
    )

    if major != 3 or (major == 3 and minor < 6):
        print(
            f"What requires Python 3.6+, you are using {python_version}. Please install a higher Python version."
        )
        sys.exit(1)

    from pywhat import what

    if len(sys.argv) == 1:
        what.main(["--help"])

    what.main()
