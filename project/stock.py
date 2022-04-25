from foreign_trade import *
from local_trade import *
from sync_API import *
import requests
import time

def main():
    foreign_dic = {'T':'NYS','INTC':'NAS','KO':'NYS','SO':'NYS','MRK':'NYS','C':'NYS'}
    local_dic = {}
    flag = 0
    ruf = 1

    try:
        #ACCESS_TOKEN = token()
        #print(ACCESS_TOKEN)

        #토큰 갱신 필요
        ACCESS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ0b2tlbiIsImF1ZCI6IjFkNmE0NzJiLTFjZmItNGNmMy05NTNlLTI4YjQyN2VhZjA4MiIsImlzcyI6InVub2d3IiwiZXhwIjoxNjUwOTQyMjQ2LCJpYXQiOjE2NTA4NTU4NDYsImp0aSI6IlBTQktscW9ZNXZTYWxmbVQ3RFZkZEwwOWcyZHh2cXI2cWVPUiJ9.8LyjUX_mcVFbRQsg8hn4aQyzQ3UfqCuL9JWPboowxEJ5yRINnAV6OjTuqGr0oz4sS3PFV_rdzPMTfj877t6nIA'
        local_val = loc_trade.loc_search(ACCESS_TOKEN,'J','005930')

        while flag < ruf:
            print("갱신중... 주기 1 sec...")
            flag = flag+1
            for key,value in foreign_dic.items():
                time.sleep(1)
                foreign_val = for_trade.foreign_search(ACCESS_TOKEN, value, key)
                foreign_price = foreign_val['output']['prpr'] if foreign_val['output'].get('prpr') else foreign_val['output'].get('last')
                for_trade.foreign_trade(ACCESS_TOKEN, value, key, foreign_price)
                print(foreign_val['output'])
                #print(f'{key} : {foreign_price}')

    except Exception as e:
        print(f"error:{e}")

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

if __name__ == '__main__':
    main()