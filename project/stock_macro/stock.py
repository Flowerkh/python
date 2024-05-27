import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname('/var/project/python/project/stock_macro'))))
from foreign_trade import *
from sync_API import *
import requests
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname('/var/project/python/kakao'))))
from kakao import send

"""
NYS : 뉴욕
AMS : 아멕스
NAS : 나스닥
"""
def main():
    time = datetime.today().strftime("%H:%M:%S")

    f = open("/var/project/python/project/stock_macro/token.txt", 'r', encoding='utf-8')
    #f = open("./token.txt", 'r', encoding='utf-8')

    url = "https://quotation-api-cdn.dunamu.com/v1/forex/recent?codes=FRX.KRWUSD"
    result = requests.get(url)
    if result.status_code == 200:
        json_data = json.loads(result.text)
        dollor = float(json.dumps(json_data[0]['basePrice'], ensure_ascii=False).strip('"'))

        try:
            line = f.readline()
            ACCESS_TOKEN = line

            # 종목 금액 조회
            QQQY = usd_search(ACCESS_TOKEN, "NAS", 'QQQY')  # 나스닥 QQQY
            QQQM = usd_search(ACCESS_TOKEN, "NAS", 'QQQM')  # 나스닥 QQQM
            SCHD = usd_search(ACCESS_TOKEN, "AMS", 'SCHD')  # 아맥스 SCHD
            SPLG = usd_search(ACCESS_TOKEN, "AMS", 'SPLG')  # 뉴욕 SPLG

            # 종목 환전 금액 (달러 > 원화)
            qqqm_price = float(QQQM['last']) * dollor
            qqqy_price = float(QQQY['last']) * dollor
            schd_price = float(SCHD['last']) * dollor
            splg_price = float(SPLG['last']) * dollor

            msg = f"환율 : {dollor}" \
                  f"\nQQQM : {round(qqqm_price, 2)} 원(${round(float(QQQM['last']), 2)})" \
                  f"\nQQQY : {round(qqqy_price, 2)} 원(${round(float(QQQY['last']), 2)})" \
                  f"\nSCHD : {round(schd_price, 2)} 원(${round(float(SCHD['last']), 2)})" \
                  f"\nSPLG : {round(splg_price, 2)} 원(${round(float(SPLG['last']), 2)})"

            # SPLG 구매
            if splg_price <= 100000:
                price = round(float(SPLG['last']), 2)
                result = trade(ACCESS_TOKEN, 'AMEX', 'SPLG', str(price))
                msg = msg + f'\n[{time}] SPLG 구매({result["msg1"]})'
            # QQQY 구매
            if qqqy_price <= 21000:
                price = round(float(QQQY['last']), 2)
                result = trade(ACCESS_TOKEN, 'NASD', 'QQQY', str(price))
                msg = msg + f'\n[{time}] QQQY 구매({result["msg1"]})'

            # 현재 해외 잔고
            info_result = info(ACCESS_TOKEN, "NASD")
            msg = msg + "\n★★★수익률★★★"
            for info_data in info_result:
                msg = msg + f"\n{info_data['ovrs_pdno']}({info_data['ord_psbl_qty']}) : {info_data['evlu_pfls_rt']}%"

            print(msg)
            # 카카오 메신저 발송
            send.kakao(msg)

        except Exception as e:
            print(f'Error [%s]' % (str(e)))
            f = open("/var/project/python/project/stock_macro/token.txt", 'w', encoding='utf-8')
            #f = open("./token.txt", 'w', encoding='utf-8')
            f.write(token())  # 토큰 없으면 생성
    else:
        print("error03 : "+result.status_code)

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
    main()