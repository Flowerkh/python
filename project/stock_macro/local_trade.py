from stock import *

class loc_trade:
    def loc_search(ACCESS_TOKEN, KIND, CODE):
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
