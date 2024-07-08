import requests
import json

url = f"http://www.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey=EMJld60MM2JVYvmBkwGSp1fDe1HEIDrg&searchdate=20240708&data=AP01"
result = requests.get(url)
if result.status_code == 200:
    json_data = json.loads(result.text)
    for jd in json_data:
        if jd['cur_unit'] == 'USD':
            USD = jd['deal_bas_r'].replace(",", "")

print(USD)