import json

def get_config():
	try:
		with open('KIS_key.json') as json_file:
			json_data = json.load(json_file)
	except Exception as e:
		print('LOG: Error in reading config file, {}'.format(e))
		return None
	else:
		return json_data

config = get_config()

class Sync_API:
    def __init__(self, config):
        self.config = config

    APP_KEY = config['app_key']
    APP_SECRET = config['app_secret']
    URL_BASE = "https://openapi.koreainvestment.com:9443"
    PATH = "/oauth2/tokenP"
    out_pr_PATH = "/uapi/overseas-price/v1/quotations/price"
    in_pr_PATH = "uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials",
            "appkey": APP_KEY,
            "appsecret": APP_SECRET}

class hash_KEY:
    def __init__(self, config):
        self.config = config

    APP_KEY = config['app_key']
    APP_SECRET = config['app_secret']
    headers = {"content-type": "application/json",
               'appKey': APP_KEY,
               'appSecret': APP_SECRET
               }
    datas = {
        "CANO": '00000000',
        "ACNT_PRDT_CD": "01",
        "OVRS_EXCG_CD": "SHAA",
        "PDNO": "00001",
        "ORD_QTY": "500",
        "OVRS_ORD_UNPR": "52.65",
        "ORD_SVR_DVSN_CD": "0"
    }
    PATH = "uapi/hashkey"
