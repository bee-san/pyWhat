import json

with open("pywhat/Data/regex.json") as file:
    database = json.load(file)


for regex in database:
    if "Matches" in regex:
        regex["Examples"] = {"Valid": regex["Matches"], "Invalid": []}
        del regex["Matches"]

with open("pywhat/Data/regex.json", "w") as file:
    json.dump(database, file)
