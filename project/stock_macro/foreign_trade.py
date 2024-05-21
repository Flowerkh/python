import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from stock import *

class for_trade:
    # 종목 조회
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
                   "tr_id": "TTTT1002U",
                   "custtype": "P",
                   "hashkey": hashkey(data)}
        res = requests.post(URL, headers=headers, data=json.dumps(data))

        return res.json()

    #해외 잔고
    def my_info(ACCESS_TOKEN, KIND):
        URL = f"{Sync_API.URL_BASE}/{Sync_API.foreign_info_PATH}"
        params = {
                "CANO": Sync_API.ACCOUNT,
                "ACNT_PRDT_CD": Sync_API.SUB_ACCOUNT,
                "OVRS_EXCG_CD": KIND,
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": ""
                }

        headers = {"Content-Type": "application/json",
                   "authorization": f"Bearer {ACCESS_TOKEN}",
                   "appKey": Sync_API.APP_KEY,
                   "appSecret": Sync_API.APP_SECRET,
                   "custtype": "P",
                   "tr_id": "TTTS3012R", #실전 : TTTS3012R, 모의 : VTTS3012R
                   "hashkey": hashkey(params)
                   }

        res = requests.get(URL, headers=headers, params=params)

        return res.json()['output1']