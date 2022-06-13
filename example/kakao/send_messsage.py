import requests
import json

# 발행한 토큰 불러오기
with open("kakao_code.json", "r") as kakao:
    kaka_tks = json.load(kakao)

kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
headers = {"Authorization": "Bearer " + kaka_tks["access_token"] }

data = {
    'object_type': 'text',
    'text': '테스트입니다.',
    'link': {
        'web_url': 'https://developers.kakao.com',
        'mobile_web_url': 'https://developers.kakao.com'
    },
}

data = {'template_object': json.dumps(data)}
response = requests.post(kakao_url, headers=headers, data=data)
print(response)
response.status_code