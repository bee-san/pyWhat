import json
import re

import requests
import wikitextparser as wtp


def cleanhtml(raw_html):
    cleanr = re.compile("<.*?>")
    cleantext = re.sub(cleanr, "", raw_html)
    return (
        cleantext.replace("\n", " ")
        .replace("\t", " ")
        .replace("{", "")
        .replace("}", "")
        .replace("|", "")
        .replace("<", "")
        .replace(">", "")
        .replace("show file signature", "")
        .replace("[[", "")
        .replace("]]", "")
        .replace("web url", "")
        .replace("cite", "")
        .strip()
    )


r = requests.get(
    "https://en.wikipedia.org/w/index.php?title=" + "List_of_file_signatures&action=raw"
)
wt = wtp.parse(r.text)
# prints first 3 items of json, delete [0:3] to print all.

sig_dict = {"root": wt.tables[0].data()}
to_iter = sig_dict["root"]
to_dump = []

populars = {"23 21"}

for i in range(1, len(to_iter)):
    to_insert = {}
    to_insert["Hexadecimal File Signature"] = cleanhtml(to_iter[i][0]).replace(" ", "")
    check_iso = cleanhtml(to_iter[i][1])
    if len(set(check_iso)) <= 2:
        to_insert["ISO 8859-1"] = None
    else:
        to_insert["ISO 8859-1"] = check_iso
    check = to_iter[i][3]
    if check == "":
        to_insert["Filename Extension"] = None
    else:
        to_insert["Filename Extension"] = cleanhtml(check)

    des = to_iter[i][4]
    if "url" in des:
        splits = des.split("=")
        if "|" in splits[1]:
            # https://wiki.wireshark.org/Development/LibpcapFileFormat#Global_Header|title
            split_more = splits[1].split("|")
            print(split_more)
            to_insert["URL"] = split_more[0]
        else:
            to_insert["URL"] = splits[1]
        to_insert["Description"] = cleanhtml(splits[0])
    else:
        to_insert["Description"] = cleanhtml(to_iter[i][4])

    if to_insert["Hexadecimal File Signature"] in populars:
        to_insert["Popular"] = 1
    else:
        to_insert["Popular"] = 0
    to_dump.append(to_insert)

with open("file_signatures.json", "w") as outfile:
    json.dump(to_dump, outfile, indent=4)

# https://en.wikipedia.org/api/rest_v1/page/html/List_of_file_signatures

"""
{
  "root": [
    [
      "[[Hexadecimal|Hex]] signature",
      "ISO 8859-1",
      "[[Offset (computer science)|Offset]]",
      "[[Filename extension]]",
      "Description"
    ],
    [
      "<pre>23 21</pre>",
      "{{show file signature|23 21}}",
      "0",
      "",
      "Script or data to be passed to the program following the [[Shebang (Unix)|shebang]] (#!)"
    ],
    [
      "<pre>a1 b2 c3 d4</pre>\n<pre>d4 c3 b2 a1</pre>",
      "{{show file signature|a1 b2 c3 d4}}\n{{show file signature|d4 c3 b2 a1}}",
      "0",
      "pcap",
      "Libpcap File Format<ref>{{cite web |url=https://wiki.wireshark.org/Development/LibpcapFileFormat#Global_Header|title=Libpcap File Format|access-date=2018-06-19}}</ref>"
    ]
  ]
}
"""
