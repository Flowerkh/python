import requests
import json

key = "EMJld60MM2JVYvmBkwGSp1fDe1HEIDrg"
url = f"https://www.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={key}&searchdate=20240627&data=AP01"
result = requests.get(url)
if result.status_code == 200:
    json_data = json.loads(result.text)
    for jd in json_data:
        if jd['cur_unit'] == 'USD':
            USD = jd['deal_bas_r'].replace(",","")

print(USD)