import requests
import json

def kakao(msg) :
    with open("/var/project/python/kakao/kakao_code.json", "r") as kakao:
    #with open("C:/project/python/python/kakao/kakao_code.json", "r") as kakao:
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
    try:
        requests.post(kakao_url, headers=headers, data=data)
    except Exception as e:
        print(f'kakao Error [%s]' % (str(e)))