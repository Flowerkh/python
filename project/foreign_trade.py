from stock import *
from sync_API import *
import requests

class for_trade:

    def foreign_search(ACCESS_TOKEN, KIND, CODE):
        URL = f"{Sync_API.URL_BASE}/{Sync_API.foreign_pr_PATH}"
        headers = {"Content-Type": "application/json",
                   "authorization": f"Bearer {ACCESS_TOKEN}",
                   "appKey": Sync_API.APP_KEY,
                   "appSecret": Sync_API.APP_SECRET,
                   "tr_id": "HHDFS00000300"
                   }
        params = {"AUTH": "", "EXCD": KIND, "SYMB": CODE}
        res = requests.get(URL, headers=headers, params=params)

        return res.json()

    # 종목 구매
    def foreign_trade(ACCESS_TOKEN, KIND, CODE, price):
        URL = f"{Sync_API.URL_BASE}/{Sync_API.foreign_pay_PATH}"
        data = {"CANO": Sync_API.ACCOUNT,
                "ACNT_PRDT_CD": "01",
                "OVRS_EXCG_CD": KIND,
                "PDNO": CODE,
                "ORD_QTY": "1",
                "OVRS_ORD_UNPR": price,
                "CTAC_TLNO": "",
                "MGCO_APTM_ODNO": "",
                "ORD_SVR_DVSN_CD": "0",
                "ORD_DVSN": "00"
                }
        headers = {"Content-Type": "application/json",
                   "authorization": f"Bearer {ACCESS_TOKEN}",
                   "appKey": Sync_API.APP_KEY,
                   "appSecret": Sync_API.APP_SECRET,
                   "tr_id": "JTTT1002U",
                   "custtype": "P",
                   "hashkey": hashkey(data)}
        res = requests.post(URL, headers=headers, data=json.dumps(data))
        return res.json()