import requests
import re
from bs4 import BeautifulSoup

char_name = '카리요'
url = 'https://lostark.game.onstove.com/Profile/Character/'+char_name
response = requests.get(url)

if response.status_code == 200:
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    char_list = soup.select('#expand-character-list > ul > li > span > button > span')
    c_list = []
    black_list = []
    path = "../discord/blacklist/black_list.txt"
    t = open(path, "r", encoding="utf-8")
    lines = t.readlines()
    char_list = soup.select('#expand-character-list > ul > li > span > button > span')
    char_list_arr = []
    test = []
    for line in lines:
        black_list.append(line.strip('\n'))

    for val in char_list:
        c_list.append(re.sub('<.+?>', '', str(val)))
    for s1 in c_list:
        for s2 in black_list:
            if s1==s2:
                test.append(s1);

    if len(test) > 0:
        print(f'{char_name} <- 블랙리스트 당장 추방 요망!!!전과 {len(test)}범:rage::rage::rage:')
    else:
        print('블랙리스트에 포함되지 않은 유저입니다 ^^*')



else:
    print(response.status_code)