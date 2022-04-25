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
    ACCOUNT = config['account']
    URL_BASE = "https://openapi.koreainvestment.com:9443"
    PATH = "/oauth2/tokenP"
    ##해외##
    #조회
    foreign_pr_PATH = "/uapi/overseas-price/v1/quotations/price"
    #구매
    foreign_pay_PATH = "/uapi/overseas-stock/v1/trading/order"

    ##국내##
    local_pr_PATH = "uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials",
            "appkey": APP_KEY,
            "appsecret": APP_SECRET}

class hash_KEY:
    def __init__(self, config):
        self.config = config

    APP_KEY = config['app_key']
    APP_SECRET = config['app_secret']
    PATH = "uapi/hashkey"
    headers = {"content-type": "application/json",
               'appKey': APP_KEY,
               'appSecret': APP_SECRET
               }


