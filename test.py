import requests
import re
import os
from bs4 import BeautifulSoup
from collections import Counter

url = 'https://lostark.game.onstove.com/Profile/Character/포용력좋은사람'
response = requests.get(url)
path = os.path.dirname(os.path.abspath(__file__))+"/test.txt"
t = open(path, "r", encoding="utf-8")
lines = t.readlines()
black_file = []
for line in lines:
    black_file.append(line.strip('\n'))


if response.status_code == 200:
        try:
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                char_list = soup.select('#expand-character-list > ul > li > span > button > span')
                c_list = []
                for clist in char_list:
                        c_list.append(re.sub('<.+?>', '', str(clist)))
                result = Counter(c_list+list(set(black_file)))

                for key, value in dict(result.most_common(1)).items():
                        if value >= 2:
                                print(f'{key} <- 블추된 새끼임. 당장 추방 요망 전과 {Counter(black_file)[key]}범 임')
                                break
                        else:
                                print(1)

        except Exception as e:
                print(e)