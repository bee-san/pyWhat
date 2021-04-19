# id
Identify anything.

# Adding Regex
**Rarity**
How unlikely is it to be a false-positive? 1 for very unlikely, 0 for very likely.

Please place your Regex into the YAML file in sorted order of rarity.

# Use Cases

## Wannacry

You come across a new piece of malware called WantToCry. You think back to Wannacry and remember it was stopped because a researcher found a kill-switch in the code.

When a domain, hardcoded into Wannacry, was registered the virus would stop.

You use `What` to identify all the domains in the malware, and use a domain registrar API to register all the domains. If Wannacry happens again, you can stop it in minutes - not weeks.

## Faster Analysis of Pcap files

Say you have a `.pcap` file from a network attack. `What` can identify this and quickly find you:
* All hashes
* Credit card numbers
* Cryptocurrency addresses
* Social Security Numbers
* and much more.

With `what`, you can identify the important things in the pcap in seconds, not minutes.

## Anything

Anytime you have a file and you want to find structured data in it that's useful, `What` is for you.

Or if you come across some piece of text and you don't know what it is, `What` will tell you.

