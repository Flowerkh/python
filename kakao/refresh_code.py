import json
import requests

url = "https://kauth.kakao.com/oauth/token"

data = {
    "grant_type": "refresh_token",
    "client_id": "6e8d6ccad42455b8a2c0979d6c005940",
    "refresh_token": "oX1OMSC-4GcgJB20MtRP1khvivGPAulL_pKTn3y4Cj10mQAAAYeYSq6r"
}
response = requests.post(url, data=data)

print(response)

# kakao_code.json 파일 저장
tokens = response.json()
with open("kakao_code.json", "w") as fp:
    json.dump(tokens, fp)
