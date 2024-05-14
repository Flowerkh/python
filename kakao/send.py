import requests
import json

def kakao(msg) :
    #with open("/var/project/python/kakao/kakao_code.json", "r") as kakao:
    with open("../kakao/kakao_code.json", "r") as kakao:
        kaka_tks = json.load(kakao)
    kakao_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": "Bearer " + kaka_tks["access_token"]}

    data = {
        'object_type': 'text',
        'text': msg,
        'link': {
            'web_url': 'https://developers.kakao.com',
            'mobile_web_url': 'https://developers.kakao.com'
        },
    }

    # 카카오톡 메세지 전송
    data = {'template_object': json.dumps(data)}
    result = requests.post(kakao_url, headers=headers, data=data)
    print(result)