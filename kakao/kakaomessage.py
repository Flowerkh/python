import requests
import json

#https://kauth.kakao.com/oauth/authorize?client_id=6e8d6ccad42455b8a2c0979d6c005940&redirect_uri=https://example.com/oauth&response_type=code
url = 'https://kauth.kakao.com/oauth/token'
rest_api_key = '6e8d6ccad42455b8a2c0979d6c005940'
redirect_uri = 'https://example.com/oauth'
authorize_code = 'MM76_60rlAx_J0-_WuwqdqsFTltdrGcfaQiQuKIaOD8uCkXmBlJ9O0ELdAFFt7h6q3PjkAoqJVAAAAGHmEk03A'

data = {
    'grant_type':'authorization_code',
    'client_id':rest_api_key,
    'redirect_uri':redirect_uri,
    'code': authorize_code,
    }

response = requests.post(url, data=data)
tokens = response.json()
print(tokens)

with open("kakao_code.json", "w") as fp:
    json.dump(tokens, fp)
