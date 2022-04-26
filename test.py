import requests
import re
from bs4 import BeautifulSoup
from collections import Counter

url = 'https://lostark.game.onstove.com/Profile/Character/알나'
response = requests.get(url)
black_list = ['테란','여x나','류서윤','푸에람','이세계겜블러','모네창','백도사','agent','아즈웬','콜라겐스킨','준뉭','석키배마','안드레아Y','빙구구루','찍먹형캐릭터','청샨','Aglovale','리플진','첨단','황하윤여자친구','하나사랑g','탕꾸리','천안혀니','커몽시','갓막창','칠격','주먹왕두두','모노뽈리','재미를찾아']
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