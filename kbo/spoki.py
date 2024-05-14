import requests
import re
from bs4 import BeautifulSoup
import sys,os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from kakao import send

url = "https://statiz.sporki.com/?ae=&as=&cn=&cv=&da=1&de=1&hi=&lr=1&mid=stat&ml=1&o1=WAR_ALL_ADJ&o2=TPA&pa=0&pl=&po=0&qu=auto&re=0&se=0&si=&sn=30&te=&tm=&tr=&ty=0&un=&ye=2023&ys=2022";
response = requests.get(url)
if response.status_code == 200:
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    temp = soup.find_all(class_="item_box")
    title = temp[5].find('div',class_='box_head').get_text()
    game = temp[5].find_all(class_='g_schedule')
    game_list = []
    place_list = {'잠실':' [잠실] ', '문학':' [문학] ', '수원':' [수원] ', '대전':' [대전] ', '광주':' [광주] '}
    for g in game:
        game_list.append(g.get_text().replace('정보',''))

    for key in place_list.keys():
        game_list = [game_list[i].replace(key, place_list[key]) for i in range(len(game_list))]

    msg = f"☆ {re.sub('								','',title.strip())} ☆\n{game_list[0]}\n{game_list[1]}\n{game_list[2]}\n{game_list[3]}\n{game_list[4]}"
    send.kakao(msg)
