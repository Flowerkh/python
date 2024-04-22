import requests
import json
from datetime import datetime,timedelta
"""
n = int
rnSt{n}Am : {n}일 후 강수 확률(Am/Pm) (3~9)
rnSt{n} : {n}일 후 강수 확률 (8~10)
wf{n}Am : {n}일 후 날씨(Am/Pm)
wf{n} : {n}일 후 날씨예보
"""

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

#날씨
weather_3days = f"{day_plus(3)}▶{weather['wf3Am']}({weather['rnSt3Am']}%) / {weather['wf3Pm']}({weather['rnSt3Pm']}%)"
weather_4days = f"{day_plus(4)}▶{weather['wf4Am']}({weather['rnSt4Am']}%) / {weather['wf4Pm']}({weather['rnSt4Pm']}%)"
weather_5days = f"{day_plus(5)}▶{weather['wf5Am']}({weather['rnSt5Am']}%) / {weather['wf5Pm']}({weather['rnSt5Pm']}%)"
weather_6days = f"{day_plus(6)}▶{weather['wf6Am']}({weather['rnSt6Am']}%) / {weather['wf6Pm']}({weather['rnSt6Pm']}%)"
weather_7days = f"{day_plus(7)}▶{weather['wf7Am']}({weather['rnSt7Am']}%) / {weather['wf7Pm']}({weather['rnSt7Pm']}%)"


# KAKAO
with open("../kakao/kakao_code.json", "r") as kakao:
    kaka_tks = json.load(kakao)

kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
headers = {"Authorization": "Bearer " + kaka_tks["access_token"] }

data = {
    'object_type': 'text',
    'text': f"날씨 예상(날씨(강수 확률))\n"
            f"{weather_3days}\n"
            f"{weather_4days}\n"
            f"{weather_5days}\n"
            f"{weather_6days}\n"
            f"{weather_7days}\n",
    'link': {
        'web_url': 'https://developers.kakao.com',
        'mobile_web_url': 'https://developers.kakao.com'
    },
}

# 카카오톡 메세지 전송
data = {'template_object': json.dumps(data)}
response = requests.post(kakao_url, headers=headers, data=data)
response.status_code
print(response)
