import requests
import json
"""
stnld(지역) : 108(전체), 109(수도권), 133(대전), 156(광주), 159(부산), 154(제주)
"""

def kakao(msg) :
    with open("/var/project/kakao/kakao_code.json", "r") as kakao:
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
    requests.post(kakao_url, headers=headers, data=data)
    print(msg)

numOfRows = 10
dataType = "JSON"
stnId = "109"
authKey = "qEFBNuDQS0uBQTbg0JtL0g"

url = f"https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstMsgService/getWthrSituation?pageNo=1&numOfRows={numOfRows}&dataType={dataType}&stnId={stnId}&authKey={authKey}"
response = requests.get(url)
if response.status_code == 200 :
    result = json.loads(response.text)
    msg = result['response']['body']['items']['item'][0]['wfSv1'].replace("           ","")
    kakao(msg)
else :
    result = "FAIL Code : 20001"