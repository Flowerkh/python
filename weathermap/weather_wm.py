import requests
import json
#from kakao.send import kakao
import sys
sys.path.append(r'/var/project/kakao')
import kakao
"""
stnld(지역) : 108(전체), 109(수도권), 133(대전), 156(광주), 159(부산), 154(제주)
"""

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