from foreign_trade import *
from sync_API import *
import requests
import time

def main():
    try:
        #ACCESS_TOKEN = token()
        #print(ACCESS_TOKEN)
        ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ0b2tlbiIsImF1ZCI6IjI1OWZhMzYzLTE3YzgtNDBmZS05YWIyLWM5Y2U2NmM5NzdmYSIsImlzcyI6InVub2d3IiwiZXhwIjoxNjUwOTU5MTQyLCJpYXQiOjE2NTA4NzI3NDIsImp0aSI6IlBTQktscW9ZNXZTYWxmbVQ3RFZkZEwwOWcyZHh2cXI2cWVPUiJ9.DvEwdez2mjTkO3rah1-E4YTGpXgM0mIm3SSt3zI82NM9XNfxN-zOq3TfMu2vlYKK8z2kMp2er0kNDqB1mdI8wA'
        for arr in info(ACCESS_TOKEN,'NASD'):
            time.sleep(1)
            if arr['ovrs_excg_cd']=='NASD': excd='NAS'
            if arr['ovrs_excg_cd']=='NYSE': excd='NYS'
            s_price = float(arr['pchs_avg_pric'])-10
            h_price = float(arr['pchs_avg_pric'])+3

            if(s_price<=float(arr['now_pric2'])<=h_price):
                trade_val = trade(ACCESS_TOKEN, arr['ovrs_excg_cd'], arr['ovrs_pdno'], arr['now_pric2'])
                print(trade_val['msg1'])
                #print(f"{arr['ovrs_pdno']}({arr['ovrs_excg_cd']}), 평균가 : {arr['pchs_avg_pric']}, 현재가 : {arr['now_pric2']}, 차액(현재가-평균가) : {round((float(arr['now_pric2'])-float(arr['pchs_avg_pric'])),2)}, 보유수량 : {int(arr['ovrs_cblc_qty'])}")

            print(arr)

    except Exception as e:
        print(e)

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