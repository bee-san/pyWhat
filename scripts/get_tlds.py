import requests

tdls = requests.get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt")
final_string = "|".join(tdls.text.split("\n")[1:-1])

file = open("tld_list.txt" , "w")
file.write(final_string)
file.close()