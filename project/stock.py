import requests
import threading
from sync_API import *

def main():
    foreign_dic = {'T':'NYS','INTC':'NAS','KO':'NYS'}
    local_dic = {}

    try:
        #ACCESS_TOKEN = token()
        ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ0b2tlbiIsImF1ZCI6ImE5M2FmMDdlLWEyZDQtNDI0Mi1iZTNkLTk1MzAzN2MzNWZiNCIsImlzcyI6InVub2d3IiwiZXhwIjoxNjUwNjk1NTgyLCJpYXQiOjE2NTA2MDkxODIsImp0aSI6IlBTQktscW9ZNXZTYWxmbVQ3RFZkZEwwOWcyZHh2cXI2cWVPUiJ9.X-ha0StJICGQBQi22PRYITJJ8xLt2Z5X1VL6mRph2NUryMmQAwFss58rHp0Rlb0WVa6a4gL1TnFOgFU-bQCCbA'

        local_val = local_trade(ACCESS_TOKEN,'J','005930')

        for key,value in foreign_dic.items():
            foreign_val = foreign_trade(ACCESS_TOKEN, value, key)
            foreign_price = foreign_val['output']['prpr'] if foreign_val['output'].get('prpr') else foreign_val['output'].get('last')

            print(f'{key} : {foreign_price}')

    except Exception as e:
        print(e)

def token():
    URL = f"{Sync_API.URL_BASE}{Sync_API.PATH}"
    res = requests.post(URL, headers=Sync_API.headers, data=json.dumps(Sync_API.body))
    token = res.json()['access_token']

    return token

def hashkey(datas):
    hash = hash_KEY()
    URL = f"{hash.URL_BASE}/{hash.PATH}"
    res = requests.post(URL, headers=hash.headers, data=json.dumps(datas))
    hashkey = res.json()["HASH"]

    return hashkey

#해외 투자
def foreign_trade(ACCESS_TOKEN, KIND, CODE):
    URL = f"{Sync_API.URL_BASE}/{Sync_API.foreign_pr_PATH}"
    headers = {"Content-Type": "application/json",
               "authorization": f"Bearer {ACCESS_TOKEN}",
               "appKey": Sync_API.APP_KEY,
               "appSecret": Sync_API.APP_SECRET,
               "tr_id": "HHDFS00000300"
               }
    params = {"AUTH": "", "EXCD": KIND, "SYMB": CODE }
    res = requests.get(URL, headers=headers, params=params)

    return res.json()

#국내 투자
def local_trade(ACCESS_TOKEN, KIND, CODE):
    URL = f"{Sync_API.URL_BASE}/{Sync_API.local_pr_PATH}"
    headers = {"Content-Type": "application/json",
               "authorization": f"Bearer {ACCESS_TOKEN}",
               "appKey": Sync_API.APP_KEY,
               "appSecret": Sync_API.APP_SECRET,
               "tr_id": "FHKST01010100"
               }
    params = {"fid_cond_mrkt_div_code": KIND, "fid_input_iscd": CODE}
    res = requests.get(URL, headers=headers, params=params)

    return res.json()

if __name__ == '__main__':
    main()