import wikitextparser as wtp
import requests
import json

r = requests.get('http://en.wikipedia.org/w/index.php?title='
    + 'List_of_file_signatures&action=raw')
wt = wtp.parse(r.text)
print(wt)
print(json.dumps({'root': wt.tables[0].data()[0:3]}, indent=2))

#https://en.wikipedia.org/api/rest_v1/page/html/List_of_file_signatures
