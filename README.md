<p align='center'>
<img src='images/logo.png'>
<p align="center">➡️ <a href="http://discord.skerritt.blog">Discord</a> ⬅️<br>
<i>The easiest way to identify anything</i><br>
<code>pip3 install pywhat && pywhat --help</code>
</p>

<p align="center">
  <a href="http://discord.skerritt.blog"><img alt="Discord" src="https://img.shields.io/discord/754001738184392704"></a> <a href="https://pypi.org/project/pywhat/"><img alt="PyPI - Downloads" src="https://pepy.tech/badge/pywhat/month"></a>  <a href="https://twitter.com/bee_sec_san"><img alt="Twitter Follow" src="https://img.shields.io/twitter/follow/bee_sec_san?style=social"></a> <a href="https://pypi.org/project/pywhat/"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/pywhat"></a> <a href="https://pypi.org/project/pywhat/"><img alt="PyPI" src="https://img.shields.io/pypi/v/pywhat"></a>
</p>
<hr>

# 🤔 `What` is this?

![](images/main_demo.gif)

Imagine this: You come across some mysterious text 🧙‍♂️ `0x52908400098527886E0F7030069857D2E4169EE7` or `dQw4w9WgXcQ` and you wonder what it is. What do you do?

Well, with `what` all you have to do is ask `what "0x52908400098527886E0F7030069857D2E4169EE7"` and `what` will tell you!

`what`'s job is to **identify _what_ something is.** Whether it be a file or text! Or even the hex of a file! What about text _within_ files? We have that too! `what` is recursive, it will identify **everything** in text and more!

# Installation

## 🔨 Using pip

```$ pip3 install pywhat```

or

```shell
# installs optional dependencies that may improve the speed
$ pip3 install pywhat[optimize] 
```

## 🔨 On Mac?

```$ brew install pywhat```

Or for our MacPorts fans:

```$ sudo port install pywhat```

# ⚙ Use Cases

## 🦠 Wannacry

![](images/wannacry_demo.png)

You come across a new piece of malware called WantToCry. You think back to Wannacry and remember it was stopped because a researcher found a kill-switch in the code.

When a domain, hardcoded into Wannacry, was registered the virus would stop.

You use `What` to identify all the domains in the malware, and use a domain registrar API to register all the domains.

## 🦈 Faster Analysis of Pcap files

![](images/pcap_demo.gif)

Say you have a `.pcap` file from a network attack. `What` can identify this and quickly find you:

- All URLs
- Emails
- Phone numbers
- Credit card numbers
- Cryptocurrency addresses
- Social Security Numbers
- and much more.

With `what`, you can identify the important things in the pcap in seconds, not minutes.

## 🐞 Bug Bounties

You can use PyWhat to scan for things that'll make you money via bug bounties like:
* API Keys
* Webhooks
* Credentials
* and more

Run PyWhat with:

```
pywhat --include "Bug Bounty" TEXT
```

To do this.

Here are some examples 👇

### 🐙 GitHub Repository API Key Leaks

1. Download all GitHub repositories of an organisation
2. Search for anything that you can submit as a bounty, like API keys

```shell
# Download all repositories
GHUSER=CHANGEME; curl "https://api.github.com/users/$GHUSER/repos?per_page=1000" | grep -o 'git@[^"]*' | xargs -L1 git clone

# Will print when it finds things.
# Loops over all files in current directory.
find . -type f -execdir pywhat --include 'Bug Bounty' {} \;
```

### 🕷 Scan all web pages for bounties

```shell
# Recursively download all web pages of a site
wget -r -np -k https://skerritt.blog

# Will print when it finds things.
# Loops over all files in current directory.
find . -type f -execdir pywhat --include 'Bug Bounty' {} \;
```

**PS**: We support more filters than just bug bounties! Run `pywhat --tags`

## 🌌 Other Features

Anytime you have a file and you want to find structured data in it that's useful, `What` is for you.

Or if you come across some piece of text and you don't know what it is, `What` will tell you.

### 📁 File & Directory Handling

**File Opening** You can pass in a file path by `what 'this/is/a/file/path'`. `What` is smart enough to figure out it's a file!

What about a whole **directory**? `What` can handle that too! It will **recursively** search for files and output everything you need!

**Multiple inputs** You can pass several files, directories or texts at once, like `what file1 file2 this/is/a/directory 'some text'` or `find . -name '*.log' -exec what {} +`. `What` shows the file of every match, the matches in text are under `text`, and `--json` returns everything in one JSON object.

**Unicode** Files and text piped into `What` can be UTF-8, or UTF-16 or UTF-32 with a byte order mark, like the "Unicode" text files that Windows saves. `What` also searches the UTF-16 strings in binary files (like `strings -el`), which is how Windows programs store most of their text. Characters that your terminal cannot show are printed as escape sequences such as `\u20bf` instead of crashing.

### 🔍 Filtering your output

Sometimes, you only care about seeing things which are related to AWS. Or bug bounties, or cryptocurrencies!

You can filter output by using `what --rarity 0.2:0.8 --include Identifiers,URL https://skerritt.blog`. Use `what --help` to get more information.

By default, `what` only shows matches with a rarity of 0.1 or more, as matches with a lower rarity are often false positives. For example, a YouTube video ID on its own, like `dQw4w9WgXcQ`, could be any 11 random characters, so `what dQw4w9WgXcQ` finds nothing, but `what --rarity 0: dQw4w9WgXcQ` shows it. YouTube links, like `https://youtu.be/dQw4w9WgXcQ` or `youtube.com/watch?v=dQw4w9WgXcQ&t=42s`, are shown by default.

To see all filters, run `pywhat --tags`! You can also combine them, for example to see all cryptocurrency wallets minus Ripple you can do:

```console
pywhat --include "Cryptocurrency Wallet" --exclude "Ripple Wallet" 1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY
```

The names of the regexes work like tags, and many regexes have shorter alternative names too, such as `BTC Wallet` for `Bitcoin (₿) Wallet Address` or `ARN` for `Amazon Resource Name (ARN)`. To only see Bitcoin and Ethereum wallets:

```console
pywhat --include "BTC Wallet,ETH Wallet" TEXT
```

Run `pywhat --names` to see the name of every regex with its alternative names.

### 👽 Sorting, Exporting, and more!

**Sorting** You can sort the output by using `what -k rarity --reverse TEXT`. Use `what --help` to get more information.

**Top matches** Found too much? `what --top 10 TEXT` only shows the 10 most likely matches, most likely first, and `what --top 5% TEXT` the most likely 5% of them. For a directory or several inputs, these are the most likely matches of all of them. The most likely matches have the highest rarity, but fragments of a longer word or match, which boundaryless mode finds, are less likely: `what --top 1 0x52908400098527886E0F7030069857D2E4169EE7` shows the Ethereum address, not the card and social security numbers in it. `what -k likely TEXT` shows all matches in this order. In the API, `pywhat.ranking.top_matches(identified, 10)` keeps the 10 most likely matches of what `Identifier.identify()` returns, and the `"Fragment"` key of a match says whether it is a fragment.

**Exporting** You can export to json using `what --json` and results can be sent directly to a file using `what --json > file.json`.

**Progress and streaming** When a search takes a while, like on a big file or directory, progress bars show how far `What` is: how many of the regexes it has searched the file for, with the one it is searching for now, and for a directory or several inputs how many of the files it has searched. They are only shown on a terminal (on stderr if the output is redirected to a file) and go away once the search is complete, `--no-progress` turns them off. With `--stream`, `What` prints every match as soon as it finds it, instead of once the search is complete: `what --stream big.log`, or `what --stream --json big.log > matches.jsonl` for a JSON object per match, one per line. As it does not wait for all the matches, `--stream` cannot sort them (`--key`) or only show the most likely ones (`--top`), and its JSON has no `"Fragment"` key.

**Boundaryless mode** `What` has a special mode to match identifiable information within strings. By default, it is enabled in CLI but disabled in API. Use `what --help` or refer to [API Documentation](https://github.com/bee-san/pyWhat/wiki/API) for more information.

**Processing** Once a regex has found something, `What` can process it further, beyond what a regex can do. For example, the date of a Unix timestamp is added to its description: `what --rarity 0: --include "UNIX Timestamp" 1637093119` shows `Date: November 16, 2021 8:05:19 PM UTC`. Bitcoin wallet addresses have a checksum, so a match whose checksum is wrong, like `3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F`, is filtered out. Use `what --disable-processing` to turn this off.

**Verifying keys** `what --verify` asks the services whether the keys it finds are valid, and adds the answer to their description. For now it verifies Google API keys: `what --verify AIzaSyA00000000000000000000000000000000` shows `Verification: invalid, Google rejected the key (API_KEY_INVALID)`. A key that is valid but cannot use the API it was tested with (e.g. `SERVICE_DISABLED`) is reported as valid. Verification is off by default because it sends the keys to the services (over HTTPS, once per key), so only use it for keys you are allowed to test. The Exploit of a key also contains the `curl` command to verify it yourself.

**Maps** Coordinates link to Google Maps. Use `what --map osm` to link them to OpenStreetMap instead: `what --map osm '52.6169586, -1.9779857'` shows `Link: https://www.openstreetmap.org/search?query=52.6169586,-1.9779857`.

### 💬 Interactive mode

Analysing something big? Load it into memory once with `--interactive`, then search through what `What` found as often as you like, without scanning it again:

```console
$ pywhat --interactive .
pywhat> tags
pywhat> include Bug Bounty
pywhat> top 10
pywhat> more
pywhat> location:"/src", include:"Bug Bounty", exclude:"Credit Card", rarity:"0.1:0.6"
pywhat> load another/directory
```

`tags` shows the tags of the current matches and how many matches have each of them, `include TAG` and `exclude TAG` narrow the search down. `top 10` only shows the 10 most likely matches of a search (`--top 10` does this from the start) and `more` the next 10. A search combines `location:`, `include:`, `exclude:`, `rarity:` and text to look for, and every part of it has to match. Where readline is available, Tab completes commands, search keys, tags, rarities and paths. Type `help` in interactive mode to see all commands.


# 🍕 API

PyWhat has an API! Click here [https://github.com/bee-san/pyWhat/wiki/API](https://github.com/bee-san/pyWhat/wiki/API) to read about it.

You can also process the matches with your own code, for example to filter out false positives. A processor gets every match of the regexes named in `names` and returns it, possibly changed (its description, rarity, ...), or `None` to filter it out. It is an object, so it can keep state between matches:

```python
from pywhat import Identifier, Processor
from pywhat.processors import default_processors


class URLProcessor(Processor):
    names = ["Uniform Resource Locator (URL)"]

    def process(self, match):
        if "trashurl.it" in match["Matched"]:
            return None
        return match


id = Identifier(processors=[*default_processors(), URLProcessor()])
id.identify("https://trashurl.it/page")
```

`Identifier(processors=[])` or `identify(text, processors=[])` turns processing off.

To verify keys with the API, like `--verify`, add the verifiers to the processors: `Identifier(processors=[*default_processors(), *verifiers()])`, with `verifiers` from `pywhat.processors`.

To link coordinates to OpenStreetMap, like `--map osm`, add `OpenStreetMapProcessor()` from `pywhat.processors` to the processors. The link of a match is then its `"Link"`, and `pywhat.printer.get_link(match)` gives the link of any match.

To get the matches while a search goes on, `iter_identify()` is a generator which yields what `identify()` finds as soon as it is found, as `(kind, location, value)`: `kind` is `"File Signatures"` or `"Regexes"`, `location` is the file (or `"text"`) and `value` is the file signature or the match. `identify()`, `identify_inputs()` and `iter_identify()` also call `progress`, if it is given, with a `Progress` before every regex they search for and once a file has been searched:

```python
from pywhat import Identifier

id = Identifier()
for kind, location, value in id.iter_identify("big/directory", only_text=False):
    if kind == "Regexes":
        print(location, value["Matched"], value["Regex Pattern"]["Name"])


def show(progress):
    # Which file (or "text"), how many of how many files are done, how many of
    # how many regexes, and the regex that is searched for (None once done)
    print(progress.location, progress.files_done, progress.files,
          progress.regexes_done, progress.regexes, progress.regex)


id.identify("big.log", only_text=False, progress=show)
```

# 👾 Contributing

`what` not only thrives on contributors, but can't exist without them! If you want to add a new regex to check for things, you can read our documentation [here](https://github.com/bee-san/what/wiki/Adding-your-own-Regex)

If a regex is known by other names, such as an abbreviation, list them in its optional `"Alternative Names"` in [regex.json](pywhat/Data/regex.json) rather than adding them as tags. Tags are for groups of regexes, like `Bug Bounty`.

Not sure which rarity to give your regex? `python scripts/rarity_score.py 'REGEX'` estimates it from the regex itself: the more specific characters a match has to contain, like the `ghp_` of a GitHub token, the rarer it is. `python scripts/rarity_score.py --database` compares the rarities in `regex.json` with their estimates, and `--help` explains how the estimate works.

Every regex needs examples in `regex.json`, which are run as tests. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add fake API keys as examples.

We ask contributors to join the Discord for quicker discussions, but it's not needed:
<a href="http://discord.skerritt.blog"><img alt="Discord" src="https://img.shields.io/discord/754001738184392704"></a>

# 🙏 Thanks

We would like to thank [Dora](https://github.com/sdushantha/dora) for their work on a bug bounty specific regex database which we have used.

We would also like to thank [tomnomnom](https://github.com/tomnomnom) for the patterns in [gf](https://github.com/tomnomnom/gf), which some of our regexes are based on.

Some of our regexes, like cron schedules, browser user agents, ISO 8601 timestamps, UK postcodes and regex101 permalinks, are based on the community library of [regex101](https://regex101.com/library).
