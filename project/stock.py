from foreign_trade import *
from sync_API import *
import requests

def main():
    path = "./token.txt"

    try:
        f = open(path, 'r', encoding='utf-8')
        line = f.readline()
        ACCESS_TOKEN = line

        for arr in info(ACCESS_TOKEN,'NASD'):
            if arr['ovrs_excg_cd']=='NASD': excd='NAS'
            if arr['ovrs_excg_cd']=='NYSE': excd='NYS'
            price = float(arr['now_pric2']) #현재가

            if(arr['ovrs_pdno']=='AAPL'):
                if(140<price<=200):
                    print(f"{arr['ovrs_pdno']}({arr['ovrs_excg_cd']}), 평균가 : {arr['pchs_avg_pric']}, 현재가 : {arr['now_pric2']}, 차액(현재가-평균가) : {round((float(arr['now_pric2'])-float(arr['pchs_avg_pric'])),2)}, 보유수량 : {int(arr['ovrs_cblc_qty'])}")
                    #trade_val = trade(ACCESS_TOKEN, arr['ovrs_excg_cd'], arr['ovrs_pdno'], arr['now_pric2'])
                    #print(trade_val['msg1'])

    except Exception as e:
        print(e)
        f = open(path, 'w', encoding='utf-8')
        ACCESS_TOKEN = token()
        f.write(ACCESS_TOKEN)

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