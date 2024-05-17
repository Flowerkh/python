import json
'''
@조회 : foreign_pr_PATH
@구매 : foreign_pay_PATH
@잔고 : foreign_info_PATH
'''

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
    def __init__(self):
        self.config = config

    APP_KEY = config['app_key']
    APP_SECRET = config['app_secret']
    ACCOUNT = config['account']
    SUB_ACCOUNT = config['sub_account']
    URL_BASE = "https://openapi.koreainvestment.com:9443"
    PATH = "/oauth2/tokenP"

    #해외 주식
    foreign_pr_PATH = "/uapi/overseas-price/v1/quotations/price"
    foreign_pay_PATH = "/uapi/overseas-stock/v1/trading/order"
    foreign_info_PATH = "/uapi/overseas-stock/v1/trading/inquire-balance"

    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials",
            "appkey": APP_KEY,
            "appsecret": APP_SECRET}

class hash_KEY:
    def __init__(self):
        self.config = config

    APP_KEY = config['app_key']
    APP_SECRET = config['app_secret']
    PATH = "uapi/hashkey"
    headers = {"content-type": "application/json",
               'appKey': APP_KEY,
               'appSecret': APP_SECRET
               }