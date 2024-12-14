import json

# Load Configurations
file = open("config.json", "r", encoding="utf8")
config = json.load(file)
file.close()
