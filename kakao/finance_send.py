import requests
import json

# 발행한 토큰 불러오기
with open("kakao_code.json", "r") as kakao:
    kaka_tks = json.load(kakao)

kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
headers = {"Authorization": "Bearer " + kaka_tks["access_token"] }

# 환율 사이트 가져오기
# FRX.KRWUSD : 달러
# FRX.KRWJPY : 엔화
# FRX.KRWCNY : 위안
# FRX.KRWEUR : 유로
finance_url = "https://quotation-api-cdn.dunamu.com/v1/forex/recent?codes=FRX.KRWUSD,FRX.KRWJPY,FRX.KRWEUR"
finance_data = requests.get(finance_url)

if finance_data.status_code == 200:
    json_data = json.loads(finance_data.text)

    usd_price = float(json.dumps(json_data[0]['basePrice'], ensure_ascii=False).strip('"'))
    jpy_price = float(json.dumps(json_data[1]['basePrice'], ensure_ascii=False).strip('"'))
    eur_price = float(json.dumps(json_data[2]['basePrice'], ensure_ascii=False).strip('"'))
else:
    print(finance_data.status_code)

data = {
    'object_type': 'text',
    'text': f"오늘의 환율\n1.0 USD : ￦ {usd_price}\n100.0 JPY : ￦ {jpy_price}\n1.0 EUR : ￦ {eur_price}",
    'link': {
        'web_url': 'https://developers.kakao.com',
        'mobile_web_url': 'https://developers.kakao.com'
    },
}

# 카카오톡 메세지 전송
data = {'template_object': json.dumps(data)}
response = requests.post(kakao_url, headers=headers, data=data)

print(response)
print(response.text)
