from foreign_trade import *
from sync_API import *
import requests
import json
from datetime import datetime

time = datetime.now()

def main():
    url = "https://quotation-api-cdn.dunamu.com/v1/forex/recent?codes=FRX.KRWUSD"
    usd = requests.get(url)
    if usd.status_code == 200:
        json_data = json.loads(usd.text)
        dollor = float(json.dumps(json_data[0]['basePrice'],ensure_ascii=False).strip('"'))
    else:
        print(usd.status_code)
    try:
        # f = open("/home/project/stock/token.txt", 'r', encoding='utf-8')
        # w = open("/home/project/stock/log/cron_log.txt", 'a', encoding='utf-8')
        f = open("./token.txt", 'r', encoding='utf-8')
        w = open("./log/cron_log.txt", 'a', encoding='utf-8')

        line = f.readline()
        ACCESS_TOKEN = line

        for arr in info(ACCESS_TOKEN,'NASD'):
            if arr['ovrs_excg_cd']=='NASD': excd='NAS'
            if arr['ovrs_excg_cd']=='NYSE': excd='NYS'
            price = float(arr['now_pric2']) #현재가
            kor = price*dollor

            if(arr['ovrs_pdno']=='AAPL'):
                if(140<price<=155):
                    if(kor<=188000):
                        w.write(f"({time.strftime('%Y-%m-%d %H:%M:%S')}) {arr['ovrs_pdno']}({arr['ovrs_excg_cd']}), 현재가 : {arr['now_pric2']}, 평균가 : {arr['pchs_avg_pric']}, 차액(현재가-평균가) : {round((float(arr['now_pric2']) - float(arr['pchs_avg_pric'])), 2)}, 보유수량 : {int(arr['ovrs_cblc_qty'])}, KOR : {round(kor, 2)}, USD : {dollor}\n")
                        trade_val = trade(ACCESS_TOKEN, arr['ovrs_excg_cd'], arr['ovrs_pdno'], arr['now_pric2'])
                        w.write(f"{trade_val['msg1']}\n")

    except Exception as e:
        print(e)
        f = open("/home/project/stock/token.txt", 'w', encoding='utf-8')
        f.write(token())

def token():
    URL = f"{Sync_API.URL_BASE}{Sync_API.PATH}"
    res = requests.post(URL, headers=Sync_API.headers, data=json.dumps(Sync_API.body))
    print(res.json())
    token = res.json()['access_token']

    return token

def hashkey(datas):
    hash = hash_KEY
    URL = f"{Sync_API.URL_BASE}/{hash.PATH}"
    res = requests.post(URL, headers=hash.headers, data=json.dumps(datas))
    hashkey = res.json()["HASH"]

    return hashkey

def search(token,kind,code):
    val = for_trade.foreign_search(token, kind, code)
    return val['output']

def trade(token,kind,code,price):
    val = for_trade.foreign_trade(token,kind,code,price)
    return val

def info(token,kind):
    return for_trade.my_info(token, kind)

if __name__ == '__main__':
    main()