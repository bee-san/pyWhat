# id
Identify anything.

# Adding Regex
**Rarity**
How unlikely is it to be a false-positive? 1 for very unlikely, 0 for very likely.

Please place your Regex into the YAML file in sorted order of rarity.

# Use Cases

You come across a new piece of malware called WantToCry. You think back to Wannacry and remember it was stopped because a researcher found a kill-switch in the code.

When a domain, hardcoded into Wannacry, was registered the virus would stop.

You use `What` to identify all the domains in the malware, and use a domain registrar API to register all the domains. If Wannacry happens again, you can stop it in minutes - not weeks.
