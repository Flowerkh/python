import requests
import json

weapon_st = 'http://152.70.248.4:5000/userinfo/동기당'
weapon_list = requests.get(weapon_st)

if weapon_list.status_code == 200:
    json_data = json.loads(weapon_list.text)
    quality = json.dumps(json_data['Items']['무기']['Quality'], indent="\t", ensure_ascii=False).strip('"')
    weapon = json.dumps(json_data['Items']['무기']['Name'], indent="\t", ensure_ascii=False).strip('"')
    print(json.dumps(json_data, indent="\t", ensure_ascii=False).strip('"'))
else:
    print(weapon_list.status_code)