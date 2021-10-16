import json

with open("pywhat/Data/regex.json") as file:
    database = json.load(file)


with open("pywhat/Data/regex.json", "w") as file:
    json.dump(database, file, indent=3)
