import requests
import re
import os
from bs4 import BeautifulSoup
from collections import Counter

url = 'https://lostark.game.onstove.com/Profile/Character/푸에람'
response = requests.get(url)
path = os.path.dirname(os.path.abspath(__file__))+"/discord/blacklist/black_list.txt"
t = open(path, "r", encoding="utf-8")
lines = t.readlines()
black_list = []
for line in lines:
    black_list.append(line.strip('\n'))
print(black_list)
if response.status_code == 200:
        try:
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                char_list = soup.select('#expand-character-list > ul > li > span > button > span')
                c_list = []
                for list in char_list:
                        c_list.append(re.sub('<.+?>', '', str(list)))
                result = Counter(c_list+black_list)
                print(dict(result.most_common(1)))
                for key, value in dict(result.most_common(1)).items():
                        if value >= 2:
                                print(f'{key} <- 블추된 새끼임. 당장 추방 요망')
                                break
                        else:
                                print()

        except Exception as e:
                print(e)