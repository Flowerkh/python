import discord
import json
import requests
import re
import os
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

        path = "./black_list.txt"
        if message.content.startswith("/찾기 "):
            char_name = message.content.replace("/찾기 ", "")
            url = 'https://lostark.game.onstove.com/Profile/Character/' + char_name
            response = requests.get(url)
            black_list = []
            t = open(path, "r", encoding="utf-8")
            lines = t.readlines()

            for line in lines:
                black_list.append(line.strip('\n'))

            if response.status_code == 200:
                try:
                    html = response.text
                    soup = BeautifulSoup(html, 'html.parser')
                    char_list = soup.select('#expand-character-list > ul > li > span > button > span')
                    c_list = []
                    for val in char_list:
                        c_list.append(re.sub('<.+?>', '', str(val)))
                    result = Counter(c_list + list(set(black_list)))
                    for key, value in dict(result.most_common(1)).items():
                        if value >= 2:
                            await message.channel.send(f'{char_name}({key}) <- 블랙리스트 당장 추방 요망!!!전과 {Counter(black_list)[key]}범:rage::rage::rage:')
                        else:
                            await message.channel.send('블랙리스트에 포함되지 않은 유저입니다 ^^*')

                except Exception as e:
                    print(e)

        if message.content.startswith("/추가 "):
            char_name = message.content.replace("/추가 ", "")
            auth = [330308658497978370,348834554011975680,747097885446897714]
            f = open(path, 'a', encoding='utf-8')

            if message.author.id in auth:
                f.write(f"\n{char_name}")
                await message.channel.send('블랙리스트 추가완료하였습니다.')
            else:
                await message.channel.send('권한이 없습니다')

#봇 실행 함수
if __name__ == "__main__":
    client = chatbot()
    client.run(config['token'])