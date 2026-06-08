import json
import requests

url = "https://kauth.kakao.com/oauth/token"
data = {
    "grant_type": "refresh_token",
    "client_id": "6e8d6ccad42455b8a2c0979d6c005940",
    "refresh_token": "CV-Kv5SJnthICmVl--HDZxrV0PaRXq7wAAAAAgo9dGgAAAGQnu6jIpIGkKnmukNu"
}
response = requests.post(url, data=data)

print(response)

# kakao_code.json 파일 저장
tokens = response.json()
with open("/var/project/python/kakao/kakao_code.json", "w") as fp:
#with open("./kakao_code.json", "w") as fp:
    json.dump(tokens, fp)