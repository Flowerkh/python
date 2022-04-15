import discord
import requests
from bs4 import BeautifulSoup
import re
import datetime
import asyncio
import os

now = datetime.datetime.now()
time = f"{str(now.year)}-{str(now.month)}-{str(now.day)} {str(now.hour)}:{str(now.minute)}:{now.second}"

token_path = os.path.dirname(os.path.abspath(__file__))+"/token.txt"
t = open(token_path, "r", encoding="utf-8")
lines = t.readlines()
for line in lines:
    token = lines

#봇 메인 함수
class chatbot(discord.Client):

    async def on_ready(self):
        my_id = token[1]
        activity = discord.Game(name="도움말 : !help")
        await client.change_presence(status=discord.Status.online, activity=activity)
        owner = await client.fetch_user(my_id)
        await owner.send("갱하봇이 호출되었습니다.")
        print('ready')

    async def on_message(self, message):
        del_message = ['시발','씨발','좃','좆','족','새기','새끼','썅','병신','뱅신','애미','니미']
        del_message_auth = ['9889']
        path = "./log/"
        if not os.path.isdir(path): os.mkdir(path)
        f = open(path + f"chat_log_{str(now.year)}{str(now.month)}{str(now.day)}.log", 'a', encoding='utf-8')

        # 상대가 bot일 경우 응답하지 않음
        if message.author.bot:
            return None

        #메세지 log
        if(message.author.id != 963969512863039508):
            try:
                if(message.channel.recipient):
                    print(f"({time}) {message.channel} : {message.content}")
                    f.write(f"\n({time}) {message.channel} : {message.content}")
            except Exception as e:
                print(f"({time}) 채널[{message.guild.name}>{message.channel}]{message.author.name}({message.author.id}) : {message.content}")
                f.write(f"\n({time}) 채널[{message.guild.name}>{message.channel}]{message.author.name}({message.author.id}) : {message.content}")

        #도움말
        if message.content == "!help":
            embed = discord.Embed(title="Dev KyungHa", description="문의는 오픈톡", color=discord.Color.from_rgb(214,234,248))
            embed.set_author(name="갱하봇",url="https://open.kakao.com/o/sMRCemVd", icon_url="https://cdn-icons-png.flaticon.com/512/7281/7281002.png")
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/7281/7281002.png")
            embed.add_field(name="문의 사항", value="오픈톡 문의 : https://open.kakao.com/o/sMRCemVd", inline=False)
            embed.add_field(name="사용법 : ", value="!청소 0~999 : 채널 내 입력 수만큼 메세지 삭제(권한 필요)\n!로아 닉네임 (로아와 검색 > 개발중)", inline=False)
            embed.set_footer(text="로그 확인 요청 : 관리자 오픈톡 문의")
            await message.channel.send(embed=embed)

        #청소 기능
        if message.content.startswith("!청소 "):
            purge_number = message.content.replace("!청소 ", "")
            check_purge_number = purge_number.isdigit()

            if message.author.discriminator in del_message_auth:
                if check_purge_number == True:
                    await message.channel.purge(limit=int(purge_number) + 1)
                    msg = await message.channel.send(f"**{purge_number}개**의 메시지를 삭제했습니다.")
                    await asyncio.sleep(3)
                    await msg.delete()
                else:
                    await message.channel.send("올바른 값을 입력해주세요. ex)!청소 0~999")
            else:
                await message.channel.send("청소 권한이 없습니다.")

        # 검색
        if message.content.startswith("!로아 "):
            char_name = message.content.replace("!로아 ", "")
            url = 'https://lostark.game.onstove.com/Profile/Character/' + char_name
            response = requests.get(url)
            if response.status_code == 200:
                try:
                    html = response.text
                    soup = BeautifulSoup(html, 'html.parser')
                    char_stat = []
                    char_jem = []
                    jem_lev_list = []
                    user_jem_lev = []
                    jem_lev = {
                        '2.00% 감소': 1, '4.00% 감소': 2, '6.00% 감소': 3, '8.00% 감소': 4, '10.00% 감소': 5, '12.00% 감소': 6,'14.00% 감소': 7, '16.00% 감소': 8, '18.00% 감소': 9, '20.00% 감소': 10,
                        '3.00% 증가': 1, '6.00% 증가': 2, '9.00% 증가': 3, '12.00% 증가': 4, '15.00% 증가': 5, '18.00% 증가': 6,'21.00% 증가': 7, '40.00% 증가': 8, '30.00% 증가': 9, '40.00% 증가': 10
                    }
                    # 캐릭터 정보
                    # embed = discord 노출
                    char_img = soup.select_one('#lostark-wrapper > div > main > div > div.profile-character-info > img').get('src')
                    char_honor = soup.select_one('#lostark-wrapper > div > main > div > div.profile-ingame > div.profile-info > div.game-info > div.game-info__title > span:nth-child(2)').get_text()  # 칭호
                    char_wj_lv = soup.select_one('#lostark-wrapper > div > main > div > div.profile-ingame > div.profile-info > div.level-info > div.level-info__expedition > span:nth-child(2)').get_text().replace('Lv.', '')  # 원정대
                    char_ft_lv = soup.select_one('#lostark-wrapper > div > main > div > div.profile-ingame > div.profile-info > div.level-info > div.level-info__item > span:nth-child(2)').get_text().replace('Lv.', '')  # 전투
                    char_item_lv = soup.select_one('#lostark-wrapper > div > main > div > div.profile-ingame > div.profile-info > div.level-info2 > div.level-info2__expedition > span:nth-child(2)').get_text().replace('Lv.', '')  # 아이템
                    char_hp = soup.select_one('#profile-ability > div.profile-ability-basic > ul > li:nth-child(2) > span:nth-child(2)').get_text()  # 최생
                    char_stat_list = soup.select_one('#profile-ability > div.profile-ability-battle > ul')  # status
                    char_card_set1 = soup.select('#cardSetList > li > div.card-effect__title') #card_setting
                    char_card_set2 = soup.select('#cardSetList > li > div.card-effect__dsc') #card_option
                    lis = char_stat_list.findAll("span")
                    for li in lis:
                        li = re.sub('<.+?>', '', str(li))
                        char_stat.append(li)

                    embed = discord.Embed(title=f"[Lv. {char_ft_lv} | {char_honor}] {char_name}", description=f"{char_item_lv} | 원정대 : {char_wj_lv}")
                    embed.set_author(name="전투정보실", url=url, icon_url="https://cdn-icons-png.flaticon.com/512/7281/7281002.png")
                    embed.set_thumbnail(url=char_img)
                    embed.add_field(name="특성",value=f"최대생명력 : {char_hp}\n{char_stat[0]}:{char_stat[1]}\t\t{char_stat[2]}:{char_stat[3]}\t\t{char_stat[6]}:{char_stat[7]}\n{char_stat[4]}:{char_stat[5]}\t\t{char_stat[8]}:{char_stat[9]}\t\t{char_stat[10]}:{char_stat[11]}", inline=False)
                    try:
                        char_jewel = soup.select_one('#profile-jewel > div > div.jewel-effect__list > div > ul')
                        jewl_list = char_jewel.findAll("p")
                        for jewel in jewl_list:
                            char_jem.append(re.sub('<.+?>', '', str(jewel)))
                            jem_lev_list.append(re.sub('<.+?>', '', str(jewel))[-9:])
                        cnt = 0
                        for lev in jem_lev_list:
                            if (lev.find('감소') > 0):
                                user_jem_lev.append(f"홍염 {jem_lev[lev]} : {char_jem[cnt]}")
                            else:
                                user_jem_lev.append(f"멸화 {jem_lev[lev]} : {char_jem[cnt]}")
                            cnt += 1
                        embed.add_field(name="보석", value=('\n').join(user_jem_lev), inline=False)
                    except Exception as e:
                        embed.add_field(name="보석", value='보석이 없습니다.', inline=False)
                    try:
                        embed.add_field(name="카드", value=f"{re.sub('<.+?>', '', str(char_card_set1.pop()))} : {re.sub('<.+?>', '', str(char_card_set2.pop()))}", inline=False)
                    except Exception as e:
                        embed.add_field(name="카드", value='장착중인 카드 효과가 없습니다.', inline=False)

                    embed.set_footer(text="※ 현재 티어3 기준으로 개발되어있습니다.\n※ 카드 효과는 가독성을 위하여 최종 적용되는 효과만 나타납니다.")
                    # discord 출력
                    await message.channel.send(embed=embed)
                except Exception as e:
                    msg = await message.channel.send(f"{char_name} : 닉네임을 다시 확인해주세요.")
                    await asyncio.sleep(3)
                    await msg.delete()
            else:
                print(response.status_code)

        #비속어 필터
        for val in del_message:
            if message.content.find(val) >= 0:
                await message.delete()
                msg = await message.channel.send(f"{message.author.mention} 님이 비속어를 사용하였습니다. 욕하지 마십쇼 ^^")
                await asyncio.sleep(3)
                await msg.delete()
                return None

#봇 실행 함수
if __name__ == "__main__":
    client = chatbot()
    client.run(token[0])