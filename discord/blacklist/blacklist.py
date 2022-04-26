import discord
import json
import requests
import re
import asyncio
from bs4 import BeautifulSoup
from collections import Counter

def get_config():
	try:
		with open('token.json') as json_file:
			json_data = json.load(json_file)
	except Exception as e:
		print('LOG: Error in reading config file, {}'.format(e))
		return None
	else:
		return json_data

config = get_config()
#봇 메인 함수
class chatbot(discord.Client):

    async def on_ready(self):
        activity = discord.Game(name="/찾기 닉네임")
        await client.change_presence(status=discord.Status.online, activity=activity)
        owner = await client.fetch_user(config['id'])
        await owner.send("blacklist 봇 실행")
        print('b_ready')

    async def on_message(self, message):
        black_list = ['테란', '여x나', '류서윤', '푸에람', '이세계겜블러', '모네창', '백도사', 'agent', '아즈웬', '콜라겐스킨', '준뉭', '석키배마', '안드레아Y',
                      '빙구구루', '찍먹형캐릭터', '청샨', 'Aglovale', '리플진', '첨단', '황하윤여자친구', '하나사랑g', '탕꾸리', '천안혀니', '커몽시', '갓막창',
                      '칠격', '주먹왕두두', '모노뽈리', '재미를찾아'
                      ]
        if message.content.startswith("/찾기 "):
            char_name = message.content.replace("/찾기 ", "")
            url = 'https://lostark.game.onstove.com/Profile/Character/' + char_name
            response = requests.get(url)
            i = 0
            if response.status_code == 200:
                try:
                    html = response.text
                    soup = BeautifulSoup(html, 'html.parser')
                    char_list = soup.select('#expand-character-list > ul > li > span > button > span')
                    c_list = []
                    for list in char_list:
                        c_list.append(re.sub('<.+?>', '', str(list)))
                    result = Counter(c_list + black_list)
                    for key, value in dict(result.most_common(1)).items():
                        if value >= 2:
                            await message.channel.send(f'{char_name}({key}) <- 블랙리스트 당장 추방 요망!!!!!:rage::rage::rage:')
                        else:
                            await message.channel.send('블랙리스트에 포함되지 않은 유저입니다 ^^*')

                except Exception as e:
                    print(e)



#봇 실행 함수
if __name__ == "__main__":
    client = chatbot()
    client.run(config['token'])