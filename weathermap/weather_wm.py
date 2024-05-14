import requests
import json
import re
from datetime import datetime

#카카오 발송
def kakao(msg) :
    with open("/var/project/python/kakao/kakao_code.json", "r") as kakao:
    #with open("../kakao/kakao_code.json", "r") as kakao:
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

def file(file_name) :
    w_msg = re.sub('(#.+)|(=)|(\$.+)|#', '', response.text)
    w_msg = re.sub(' +', ' ', w_msg)
    w_msg = re.sub('"', '', w_msg)
    with open(file_name, 'w') as f:
        f.write(w_msg)
    with open(file_name, 'r') as f:
        lines = f.readlines()
        lines = [line.rstrip('\n') for line in lines]
    return lines

#강수유무
def PRE(value) :
    pre = {"WB09":" / 비", "WB11":" / 비/눈", "WB13":" / 눈/비", "WB12":" / 눈"}.get(value, "")
    return pre

"""
stnld(지역) : 108(전체), 109(수도권), 133(대전), 156(광주), 159(부산), 154(제주)
reg(지역) : 11B10101(서울), 11B20601(수원), 11C20401(대전), 11F20501(광주), 11H10701(대구), 11H20201(부산)
f_reg(지역) : 11B00000(수도권), 
"""
today = datetime.today().strftime("%Y-%m-%d")
reg = "11B10101"
f_reg = "11B00000"
authKey = "qEFBNuDQS0uBQTbg0JtL0g"

w_url = f"https://apihub.kma.go.kr/api/typ01/url/fct_afs_wc.php?reg={reg}&mode=0&disp=1&help=0&authKey={authKey}"
response = requests.get(w_url)
if response.status_code == 200:
    w_lines = file('weather_text')
    min_tmp = w_lines[2].split(',')[6]
    max_tmp = w_lines[2].split(',')[7]

    wf_url = f"https://apihub.kma.go.kr/api/typ01/url/fct_afs_wl.php?reg={f_reg}&mode=0&disp=1&help=0&authKey={authKey}"
    response = requests.get(wf_url)
    if response.status_code == 200:
        f_lines = file('fweather_text')
        pre = PRE(f_lines[2].split(',')[7]) #강수유무
        rn_st = f_lines[2].split(',')[10] #강수확률
        wf = f_lines[2].split(',')[9] #하늘상태

        msg = f"{today}\n수도권({wf}{pre})\n기온 : {min_tmp}° / {max_tmp}°\n강수 확률 : {rn_st}%"
        kakao(msg)
    else:
        print("FAIL Code : 20002")
else:
    result = "FAIL Code : 20001"