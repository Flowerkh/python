
import requests
import re
from datetime import datetime,timedelta
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from kakao import send

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
tomorrow = datetime.today()+timedelta(days=1)
tomorrow = tomorrow.strftime("%Y-%m-%d")
reg = "11B10101"
f_reg = "11B00000"
authKey = "qEFBNuDQS0uBQTbg0JtL0g"

w_url = f"https://apihub.kma.go.kr/api/typ01/url/fct_afs_wc.php?reg={reg}&mode=0&disp=1&help=0&authKey={authKey}"
response = requests.get(w_url)
if response.status_code == 200:
    w_lines = file('weather_text')
    today_min_tmp = w_lines[2].split(',')[6]
    today_max_tmp = w_lines[2].split(',')[7]
    # tomorrow_min_tmp = w_lines[3].split(',')[6]
    # tomorrow_max_tmp = w_lines[3].split(',')[7]

    wf_url = f"https://apihub.kma.go.kr/api/typ01/url/fct_afs_wl.php?reg={f_reg}&mode=0&disp=1&help=0&authKey={authKey}"
    response = requests.get(wf_url)
    if response.status_code == 200:
        f_lines = file('fweather_text')
        to_pre = PRE(f_lines[2].split(',')[7])  # 강수유무
        to_rn_st = f_lines[2].split(',')[10]  # 강수확률
        to_wf = f_lines[2].split(',')[9]  # 하늘상태

        # ne_pre = PRE(f_lines[3].split(',')[7])  # 강수유무
        # ne_rn_st = f_lines[3].split(',')[10]  # 강수확률
        # ne_wf = f_lines[3].split(',')[9]  # 하늘상태

        msg = f"{today}\n수도권({to_wf}{to_pre})\n기온 : {today_min_tmp}° / {today_max_tmp}°\n강수 확률 : {to_rn_st}%\n\n"
        send.kakao(msg)
    else:
        print("FAIL Code : 20002")
else:
    result = "FAIL Code : 20001"