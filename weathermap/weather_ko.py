import requests
import json
from datetime import datetime,timedelta

url = 'http://apis.data.go.kr/1360000/MidFcstInfoService/getMidLandFcst'
Key = 'sxbRIn8O3zpisPkZQ2a11s2K3N1yG8a90bDZRV6+b65d/u+oRzWVfwZtcpHwQ1jV6iKu4TvEWSbHT5qCNImVxw=='

now = datetime.now()
today = datetime.today().strftime('%Y%m%d')+'0600'
params ={'serviceKey':Key, 'pageNo':'1', 'numOfRows':'10', 'dataType':'JSON', 'regId':'11B00000', 'tmFc':today}

response = requests.get(url, params=params)
result = json.loads(response.text)
weather = result['response']['body']['items']['item'][0]

#날짜 더하기
def day_plus(day) :
    return (datetime.now() + timedelta(days=day)).strftime('%m/%d')

#강수량
precipitation_3days = f"{weather['rnSt3Am']}~{weather['rnSt3Pm']}"
precipitation_4days = f"{weather['rnSt4Am']}~{weather['rnSt4Pm']}"
precipitation_5days = f"{weather['rnSt5Am']}~{weather['rnSt5Pm']}"
precipitation_6days = f"{weather['rnSt6Am']}~{weather['rnSt6Pm']}"
precipitation_7days = f"{weather['rnSt7Am']}~{weather['rnSt7Pm']}"

#날씨
weather_3days = f"{day_plus(3)}▶AM:{weather['wf3Am']} PM:{weather['wf3Pm']}"
weather_4days = f"{day_plus(4)}▶AM:{weather['wf4Am']} PM:{weather['wf4Pm']}"
weather_5days = f"{day_plus(5)}▶AM:{weather['wf5Am']} PM:{weather['wf5Pm']}"
weather_6days = f"{day_plus(6)}▶AM:{weather['wf6Am']} PM:{weather['wf6Pm']}"
weather_7days = f"{day_plus(7)}▶AM:{weather['wf7Am']} PM:{weather['wf7Pm']}"


# KAKAO
with open("../kakao/kakao_code.json", "r") as kakao:
    kaka_tks = json.load(kakao)

kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
headers = {"Authorization": "Bearer " + kaka_tks["access_token"] }

data = {
    'object_type': 'text',
    'text': f"날씨 예상\n"
            f"{weather_3days}({precipitation_3days})\n"
            f"{weather_4days}({precipitation_4days})\n"
            f"{weather_5days}({precipitation_5days})\n"
            f"{weather_6days}({precipitation_6days})\n"
            f"{weather_7days}({precipitation_7days})\n",
    'link': {
        'web_url': 'https://developers.kakao.com',
        'mobile_web_url': 'https://developers.kakao.com'
    },
}

# 카카오톡 메세지 전송
data = {'template_object': json.dumps(data)}
response = requests.post(kakao_url, headers=headers, data=data)
print(response)
response.status_code