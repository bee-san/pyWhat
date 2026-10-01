Please read our wiki here:
https://github.com/bee-san/pyWhat/wiki/Adding-your-own-Regex

To pick the rarity of a new regex, `python scripts/rarity_score.py 'REGEX'` estimates it from the regex.

Every regex in `pywhat/Data/regex.json` needs at least one valid example in its `"Examples"`, as the examples are run as tests. Please add invalid examples too, like values that look similar but must not match.

Secret scanners take fake API keys, like a Stripe or Shopify key, for leaked secrets: GitHub may block the push, and SonarCloud fails the pull request. To avoid that, write such an example as a list of parts, which pyWhat joins when it loads the regexes:

```json
"Valid": [
   [
      "sk_live_",
      "tkOg6ekCDvaFSDfSfyQqMfA0"
   ]
]
```
