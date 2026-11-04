# Where pyWhat's data comes from

The files in `pywhat/Data/` ship in the Python package, the Rust crate and its WebAssembly build.
This is what the repository records about where they came from.

| File | Contents | Source | Licence |
|---|---|---|---|
| `regex.json` | the regexes, with their examples | written for pyWhat, some adapted from other projects (README, "Thanks") | MIT (pyWhat), and the projects' licences |
| `file_signatures.json` | 181 file signatures (magic numbers) with descriptions | Wikipedia, [List of file signatures](https://en.wikipedia.org/wiki/List_of_file_signatures), fetched by `scripts/get_file_sigs.py` | CC BY-SA 4.0 (Wikipedia's text) |
| `mac_vendors.json` | 43,440 MAC address prefixes and their vendors | not recorded (added in e589732, 2021-08-12); the prefixes are the IEEE Registration Authority's MA-L, MA-M and MA-S assignments | not recorded |
| `phone_codes.json` | country calling codes and their countries | not recorded (added in 71cdefb, 2021-05-28) | not recorded |
| `mastercard_companies.json` | MasterCard issuer prefixes and banks | not recorded (added in 892765a, 2021-08-06) | not recorded |

Open question for the owner (raised in the Rust port, issue #291): CC BY-SA text in a package
needs attribution and share-alike, and the sources of the other three files aren't recorded. The
files have shipped on PyPI since 2021; the crate and the WebAssembly build ship them too.
