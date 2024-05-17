import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from foreign_trade import *
from sync_API import *
import requests
import json
from datetime import datetime
from kakao import send

time = datetime.now()
now = datetime.today().strftime("%Y%m%d")
now_min = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

"""
NYS : 뉴욕
AMS : 아멕스
NAS : 나스닥
"""
def main():
    f = open("/var/project/python/stock/token.txt", 'r', encoding='utf-8')
    w = open("/var/project/python/stock/log/cron_log"+now+".txt", 'a', encoding='utf-8')
    #f = open("./token.txt", 'r', encoding='utf-8')
    #w = open("./log/cron_log"+now+".txt", 'a', encoding='utf-8')

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

            # 종목 환전 금액 (달러 > 원화)
            qqqm_price = float(QQQM['last']) * dollor
            qqqy_price = float(QQQY['last']) * dollor
            schd_price = float(SCHD['last']) * dollor

            msg = f"환율 : {dollor}" \
                  f"\nQQQM : {round(qqqm_price, 2)} 원" \
                  f"\nQQQY : {round(qqqy_price, 2)} 원" \
                  f"\nSCHD : {round(schd_price, 2)} 원"

            # 현재 잔고, 구매
            #info_result = info(ACCESS_TOKEN, "NASD")

            # SCHD 구매
            if schd_price <= 110000.99:
                result = trade(ACCESS_TOKEN, 'AMS', 'SCHD', SCHD['last'])
                w.write(f'[{now_min}] SCHD 구매 : [%s]' % result)
            # QQQY 구매
            if schd_price <= 25000.99:
                result = trade(ACCESS_TOKEN, 'NAS', 'QQQY', QQQY['last'])
                w.write(f'[{now_min}] QQQY 구매 : [%s]' % result)
            send.kakao(msg)

        except Exception as e:
            w.write(f'[{now_min}] Error [%s]' % (str(e)))
            f = open("/var/project/python/stock/token.txt", 'w', encoding='utf-8')
            #f = open("./token.txt", 'w', encoding='utf-8')
            f.write(token())  # 토큰 없으면 생성
            main()
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
    val = for_trade.foreign_trade(token,kind,code,price)
    return val

#잔고
def info(token,kind):
    #NASD : 미국 전체
    #NAS : 나스닥
    #NYSE : 뉴욕
    #AMEX : 아멕스
    return for_trade.my_info(token, kind)

if __name__ == '__main__':
    main()