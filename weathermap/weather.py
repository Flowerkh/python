import requests
import json
import math

city = "Seoul"
apiKey = "7623a974beae766ea82db4a2dea7d8ac"
lang = "kr"
units = "metric"
api = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={apiKey}&lang={lang}&units={units}"

result = requests.get(api)
result = json.loads(result.text)

weather_en = result['weather'][0]['main']
weather_ko = result['weather'][0]['description']
temp = result['main']['temp']
humidity = result['main']['humidity']

# KAKAO
with open("../kakao/kakao_code.json", "r") as kakao:
    kaka_tks = json.load(kakao)

kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
headers = {"Authorization": "Bearer " + kaka_tks["access_token"] }

data = {
    'object_type': 'text',
    'text': f"오늘의 날씨\n온도 : {math.ceil(temp)} °C\n날씨 : {weather_ko}({weather_en})\n습도 : {humidity} %",
    'link': {
        'web_url': 'https://developers.kakao.com',
        'mobile_web_url': 'https://developers.kakao.com'
    },
}

# 카카오톡 메세지 전송
data = {'template_object': json.dumps(data)}
response = requests.post(kakao_url, headers=headers, data=data)
print(response.status_code)