# Where regexes come from

Most of pyWhat's regexes are written from the documentation of the format they identify. When a
regex is adapted from another project, it is listed here, and [NOTICE](../NOTICE) has the
project's copyright line and licence. Only projects under MIT, BSD, Apache-2.0, CC0, CC BY or a
public-domain dedication can be sources, as the regexes ship in the Python package and the Rust
crate (docs/adding-regexes.md). The rows below whose licence is "not stated" were added before
this rule; [#302](https://github.com/bee-san/pyWhat/issues/302) lists them, and nothing new may
come from them.

| Regexes | Project | URL | Licence |
|---|---|---|---|
| bug bounty regexes and their `Exploit` texts (#146; README, "Thanks") | Dora | https://github.com/sdushantha/dora | MIT. Dora's README says many of its regexes come from truffleHogRegexes (GPL-3.0), secretx (GPL-3.0) and nine other projects, and most of its exploitation methods from keyhacks ([#302](https://github.com/bee-san/pyWhat/issues/302)) |
| `Exploit` texts (#162) | keyhacks | https://github.com/streaak/keyhacks | not stated ([#302](https://github.com/bee-san/pyWhat/issues/302)) |
| patterns of gf (#273; README, "Thanks") | gf (tomnomnom) | https://github.com/tomnomnom/gf | MIT |
| IPv4 CIDR Block, Log4Shell (Log4j JNDI Lookup) Payload, Tox ID (#273) | patterns proposed in gf pull requests #25 (nikitastupin), #61 (jreisinger) and #84 (johndoe-sh) | https://github.com/tomnomnom/gf/pulls | MIT (gf's licence) |
| the top-level domains in Uniform Resource Locator (URL) | IANA's list of top-level domains, fetched by `scripts/get_tlds.py` | https://data.iana.org/TLD/tlds-alpha-by-domain.txt | not stated ([#302](https://github.com/bee-san/pyWhat/issues/302)) |
| Browser User Agent, Regex101 Permalink, ISO 8601 Timestamp, United Kingdom (UK) Postcode, Cron Schedule (#276) | the regex101 community library, https://regex101.com/library | [Parsing browser User Agents](https://regex101.com/r/aL8lD7/2) by OnlineCop, [regex101.com permalink id grabber](https://regex101.com/r/wY0rM7/3) by chris mccoy, [RFC3339 DateTime](https://regex101.com/r/qH0sU7/1), [UK Postcode Checker](https://regex101.com/r/tH9mQ1/1) by MaffooBristol, [Cron schedule](https://regex101.com/r/vY5eL1/1) (no author is given for the other two) | not stated by regex101 ([#302](https://github.com/bee-san/pyWhat/issues/302)) |

Regexes of the area files, one section per area so that pull requests for different areas
change different lines:

## crypto

| Regexes | Project | URL | Version | Licence |
|---|---|---|---|---|

## cloud

| Regexes | Project | URL | Version | Licence |
|---|---|---|---|---|

## ctf

| Regexes | Project | URL | Version | Licence |
|---|---|---|---|---|

## network

| Regexes | Project | URL | Version | Licence |
|---|---|---|---|---|

## ids

| Regexes | Project | URL | Version | Licence |
|---|---|---|---|---|

## files

| Regexes | Project | URL | Version | Licence |
|---|---|---|---|---|

## social

| Regexes | Project | URL | Version | Licence |
|---|---|---|---|---|
