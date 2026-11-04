# Where pyWhat's data comes from

The files in `pywhat/Data/` ship in the Python package, in the Rust crate and in its WebAssembly
build. This page lists where each came from and its licence, as far as the repository and its
history record it. [NOTICE](../NOTICE) holds the same attributions in the packages,
[regex-sources.md](regex-sources.md) the sources of regexes, and
[#302](https://github.com/bee-san/pyWhat/issues/302) the gaps and the options for them.

| File | Contents | Source | Licence |
|---|---|---|---|
| `regex.json` and `regexes/*.json` | the regexes, with their examples | written for pyWhat; the regexes and texts adapted from other projects are listed in [regex-sources.md](regex-sources.md) | MIT (pyWhat), with the attributions in NOTICE |
| `file_signatures.json` | 181 file signatures (magic numbers) with descriptions | Derived from Wikipedia's [List of file signatures](https://en.wikipedia.org/wiki/List_of_file_signatures), [revision 1021969603](https://en.wikipedia.org/w/index.php?title=List_of_file_signatures&oldid=1021969603) of 2021-05-07. `scripts/get_file_sigs.py` converted it to JSON in 9a7d21d (2021-05-09); running that script on this revision reproduces the committed file exactly. The revisions before it lack the Blender signature, which was added in this revision, and the ones before 2021-05-02 also lack GRIB. The earlier YAML of 125d654 (2021-04-01) was converted from [revision 1011793547](https://en.wikipedia.org/w/index.php?title=List_of_file_signatures&oldid=1011793547). #275 (889340a) added the byte order marks of big-endian UTF-16 and UTF-32 and corrected the descriptions of the little-endian ones. | The revision is under CC BY-SA 3.0 Unported and the GFDL. pyWhat's adaptation is under **CC BY-SA 4.0**, as section 4(b) of CC BY-SA 3.0 allows. This file and adaptations of it stay under CC BY-SA 4.0, not under pyWhat's MIT License. |
| `mac_vendors.json` | 43,440 MAC address prefixes and the organisations they are assigned to | Added in e589732 (2021-08-12, #127). The prefixes are the IEEE Registration Authority's MA-L, MA-M, MA-S and IAB assignments, and the names are the organisations' registered names, title-cased and abbreviated. The list it was copied from is not recorded. It is derived from the IEEE lists, not from Wireshark's `manuf` (GPL-2.0-or-later) or Nmap's `nmap-mac-prefixes`. 27 of its names have no-break spaces, as in the IEEE lists, where `manuf` 3.4 and `nmap-mac-prefixes` have none. It doesn't have their hand-made entries: for 000000 it has "Xerox Corp", where `manuf` has "Officially Xerox, but 0:0:0:0:0:0 is more common" and Nmap "Xerox"; 080027 is "Pcs Systemtechnik GmbH", the IEEE name title-cased, not "PCS Computer Systems GmbH" (`manuf`) or "Oracle VirtualBox virtual NIC" (Nmap); and 525400, which IEEE hasn't assigned, isn't in it. | not recorded |
| `phone_codes.json` | 228 country calling codes (ITU-T E.164) and their countries | Added in 71cdefb (2021-05-28, #52) and reworked in f1c993d (#127). 226 of the 228 entries are those of the gist [CountryCodes.json](https://gist.github.com/anubhavshrimal/75f6183458db8c453306f93521e93d37) by anubhavshrimal (2016), a fork of [Country and Dial or Phone codes in JSON format](https://gist.github.com/Goles/3196253) by Goles (2012). The other two are Kosovo (+383), which 71cdefb added, and "SuriName" for Suriname (+597), a typo from f1c993d. | not recorded; neither gist states one |

The sha256 of the files as they are now:

| File | sha256 |
|---|---|
| `file_signatures.json` | `87379143e851b922972e02d91b078bc82a6bf0ce2beb9f1664c1d4be17fc5584` |
| `mac_vendors.json` | `57b9550b9e6f6db69837f3ca173fbd6b349e7f0254ee7a301005eba96f467393` |
| `phone_codes.json` | `96b9e39a65456e49e3888f7603c338b1862addc4e643c69944436bfc2585bd80` |

**Removed in 6.0.0:** `mastercard_companies.json`, 1,175 MasterCard issuer prefixes (BINs) and the
names of their banks, which added "Issuer(s): …" to the description of MasterCard Number matches.
It was added in 892765a (2021-08-06, #127), most likely from Mastercard's
[Simplified BIN account range table](https://www.mastercard.us/en-us/business/issuers/get-support/simplified-bin-account-range-table.html),
which #51 points to: the table has the company name of each account range, and the file had 480
upper-case company names of at most 60 characters. The page's terms
([archived on 2021-08-04](https://web.archive.org/web/20210804194632/https://www.mastercard.us/en-us/business/issuers/get-support/simplified-bin-account-range-table.html),
two days before the file was added, and unchanged in 2023) say: "You may not license, sublicense,
publish, distribute, copy, reproduce in any form, sell or otherwise transfer, or create any
derivative work of or from any Content." The MasterCard Number regex and the rest of its output
stay.

The other files have shipped on PyPI since 2021. New data for pyWhat, whether a data file or a regex
adapted from another project, may only come from sources that are public domain, CC0, MIT, BSD,
Apache-2.0 or CC BY, with an attribution in NOTICE ([adding-regexes.md](adding-regexes.md)). A
new data file gets a row here with its URL, version or retrieval date, sha256 and licence.
Sources under CC BY-SA, GPL, LGPL or MPL, or without a licence, can be used for evaluation only.
