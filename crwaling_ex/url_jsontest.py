import requests
import json

url = 'https://quotation-api-cdn.dunamu.com/v1/forex/recent?codes=FRX.KRWUSD'
data_list = requests.get(url)

if data_list.status_code == 200:
    json_data = json.loads(data_list.text)
    print(json.dumps(json_data[0]['basePrice'], indent="\t", ensure_ascii=False).strip('"'))
    print(json.dumps(json_data, indent="\t", ensure_ascii=False).strip('"'))
else:
    print(data_list.status_code)