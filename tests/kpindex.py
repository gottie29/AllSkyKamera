from datetime import datetime, timedelta
import json
import requests

start       = datetime.now() - timedelta(hours = 10)
end         = datetime.now()
time_string = "start=" + start.strftime('%Y-%m-%dT%H:%M:%SZ') + "&end=" + end.strftime('%Y-%m-%dT%H:%M:%SZ')
url         = 'https://kp.gfz-potsdam.de/app/json/?' + time_string + "&index=Kp"
response    = requests.get(url)
response.raise_for_status()
data        = response.json()
data        = {"kp_index": data["Kp"][-1]}

with open("kpindex.json", 'w') as f:
    json.dump(data, f)
