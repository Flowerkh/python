import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname('/var/project/python/project/stock_macro'))))
from foreign_trade import *
from sync_API import *
import requests
import json
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname('/var/project/python/kakao'))))
from kakao import send
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

"""
NYS : 뉴욕
AMS : 아멕스
NAS : 나스닥
"""
def main():
    f = open("/var/project/python/project/stock_macro/token.txt", 'r', encoding='utf-8')
    #f = open("./token.txt", 'r', encoding='utf-8')
    dollor = 1390

    try:
        line = f.readline()
        ACCESS_TOKEN = line

        # 종목 금액 조회
        NVDA = usd_search(ACCESS_TOKEN, "NAS", 'NVDA')  # 나스닥 엔비디아
        QQQY = usd_search(ACCESS_TOKEN, "NAS", 'QQQY')  # 나스닥 QQQY
        SPLG = usd_search(ACCESS_TOKEN, "AMS", 'SPLG')  # 아맥스 SPLG
        NVDY = usd_search(ACCESS_TOKEN, "AMS", 'NVDY')  # 아맥스 NVDY

        # 종목 환전 금액 (달러 > 원화)
        nvda_price = float(NVDA['last']) * dollor
        qqqy_price = float(QQQY['last']) * dollor
        splg_price = float(SPLG['last']) * dollor
        nvdy_price = float(NVDY['last']) * dollor

        msg = f"환율 : {dollor}" \
              f"\nNVDA : {format(round(nvda_price, 2), ',')} 원(${format(round(float(NVDA['last']), 2), ',')})" \
              f"\nQQQY : {format(round(qqqy_price, 2), ',')} 원(${format(round(float(QQQY['last']), 2), ',')})" \
              f"\nSPLG : {format(round(splg_price, 2), ',')} 원(${format(round(float(SPLG['last']), 2), ',')})" \
              f"\nNVDY : {format(round(nvdy_price, 2), ',')} 원(${format(round(float(NVDY['last']), 2), ',')})"

        # 현재 해외 잔고
        info_result = info(ACCESS_TOKEN, "NASD")
        info_dic = {}
        msg = msg + "\n★★★수익률★★★"
        for info_data in info_result:
            info_dic[info_data['ovrs_pdno']] = info_data['ord_psbl_qty']
            msg = msg + f"\n{info_data['ovrs_pdno']}({info_data['ord_psbl_qty']}) : $ {round(float(info_data['ovrs_stck_evlu_amt']),2)} ({info_data['evlu_pfls_rt']}%)"

        # SPLG 구매
        if splg_price <= 100000:
            price = round(float(SPLG['last']), 2)
            trade(ACCESS_TOKEN, 'AMEX', 'SPLG', str(price))

        print(msg)
        # 카카오 메신저 발송
        # if datetime.now().strftime('%H:%M') >= "04:10":
        #send.kakao(msg)

    except Exception as e:
        print(f'Error [%s]' % (str(e)))
        f = open("/var/project/python/project/stock_macro/token.txt", 'w', encoding='utf-8')
        #f = open("./token.txt", 'w', encoding='utf-8')
        f.write(token())  # 토큰 없으면 생성



def token():
    URL = f"{Sync_API.URL_BASE}{Sync_API.PATH}"
    res = requests.post(URL, headers=Sync_API.headers, data=json.dumps(Sync_API.body))
    token = res.json()['access_token']

    return token

def hashkey(datas):
    hash = hash_KEY
    URL = f"{Sync_API.URL_BASE}/{hash.PATH}"
    res = requests.post(URL, headers=hash.headers, data=json.dumps(datas))
    hashkey = res.json()["HASH"]

    return hashkey

#가격 조회
def usd_search(token, kind, code):
    val = for_trade.foreign_search(token, kind, code)
    return val['output']

#거래
def trade(token, kind, code, price):
    #NASD : 나스닥
    #NYSE : 뉴욕
    #AMEX : 아멕스
    val = for_trade.foreign_trade(token,kind,code,price)
    return val

#잔고
def info(token,kind):
    #NASD : 미국 전체
    #NAS  : 나스닥
    #NYSE : 뉴욕
    #AMEX : 아멕스
    return for_trade.my_info(token, kind)

if __name__ == '__main__':
    # key = "EMJld60MM2JVYvmBkwGSp1fDe1HEIDrg"
    # url = f"http://www.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={key}&searchdate=20240627&data=AP01"
    #
    # result = requests.get(url, verify=False)
    # if result.status_code == 200:
    #     json_data = json.loads(result.text)
    #     for jd in json_data:
    #         if jd['cur_unit'] == 'USD':
    #             USD = float(jd['deal_bas_r'].replace(',',''))
    # else:
    #     USD = 1390

    main()