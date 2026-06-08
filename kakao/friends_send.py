import json
import requests

#친구 목록 가져오기
url = "https://kapi.kakao.com/v1/api/talk/friends"
with open("kakao_code.json", "r") as kakao:
    kaka_tks = json.load(kakao)
header = {"Authorization": 'Bearer ' + kaka_tks["access_token"]}
result = json.loads(requests.get(url, headers=header).text)
friends_list = result.get("elements")

print(result)