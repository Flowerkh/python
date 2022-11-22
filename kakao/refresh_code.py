import json

import requests

url = "https://kauth.kakao.com/oauth/token"

data = {
    "grant_type": "refresh_token",
    "client_id": "6e8d6ccad42455b8a2c0979d6c005940",
    "refresh_token": "KRRHN3Hr8UScNe79MajZrzeZ06hw9s0VHrSa-4F0CisM0gAAAYR_C1zr"
}
response = requests.post(url, data=data)
tokens = response.json()

# kakao_code.json 파일 저장
with open("kakao_code.json", "w") as fp:
    json.dump(tokens, fp)
