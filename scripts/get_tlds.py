import requests

def get_tlds():
    tdls = requests.get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt")
    final_string = "|".join(tdls.text.split("\n")[1:-1])

    return final_string