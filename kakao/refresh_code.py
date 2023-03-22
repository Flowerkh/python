import json
import requests

url = "https://kauth.kakao.com/oauth/token"

data = {
    "grant_type": "refresh_token",
    "client_id": "6e8d6ccad42455b8a2c0979d6c005940",
    "refresh_token": "Cj9AShV-swHH8lbzsgbgjc96a0uk3R9W-iudtmGMCj1zmwAAAYaf2RE4"
}
response = requests.post(url, data=data)

print(response)

# kakao_code.json 파일 저장
tokens = response.json()
with open("kakao_code.json", "w") as fp:
    json.dump(tokens, fp)
