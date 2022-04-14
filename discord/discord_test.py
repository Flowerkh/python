import discord
import datetime
import asyncio
import os

token_path = os.path.dirname(os.path.abspath(__file__))+"/token.txt"
t = open(token_path, "r", encoding="utf-8")
lines = t.readlines()
for line in lines:
    token = lines
now = datetime.datetime.now()
time = f"{str(now.year)}-{str(now.month)}-{str(now.day)} {str(now.hour)}:{str(now.minute)}:{now.second}"
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
        del_message = ['시발','씨발','좃','좆','족', '새기', '새끼', '썅', '병신', '뱅신', '애미']
        del_message_auth = ['9889']
        path = "./log/"
        if not os.path.isdir(path): os.mkdir(path)
        f = open(path + f"chat_log_{str(now.year)}{str(now.month)}{str(now.day)}.log", 'a')

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
                f.write(f"\n({time}) 채널[{message.guild.name}>{message.channel}]{message.author.name}({message.author.id}) : {message.content}")
                print(f"({time}) 채널[{message.guild.name}>{message.channel}]{message.author.name}({message.author.id}) : {message.content}")

        if message.content == "!help":
            embed = discord.Embed(title="Dev KyungHa", description="문의는 오픈톡", color=discord.Color.from_rgb(114, 158, 211))
            embed.set_author(name="갱하봇",url="https://open.kakao.com/o/sMRCemVd", icon_url="https://cdn-icons-png.flaticon.com/512/7281/7281002.png")
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/7281/7281002.png")
            embed.add_field(name="문의 사항", value="오픈톡 문의 : https://open.kakao.com/o/sMRCemVd", inline=True)
            embed.add_field(name="사용법 : ", value="!청소 0~999 : 채널 내 입력 수만큼 메세지 삭제(권한 필요)\n!닉네임 캐릭터 정보 검색 (추가 예정)", inline=False)
            embed.set_footer(text="로그 확인 요청 : 관리자 오픈톡 문의")
            await message.channel.send(embed=embed)
            return None

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

        #비속어 필터
        for val in del_message:
            if message.content.find(val) >= 0:
                await message.delete()
                msg = await message.channel.send(f"{message.author.mention} 님이 비속어를 사용하였습니다. 욕하지 마십쇼 ^^")
                await asyncio.sleep(3)
                await msg.delete()
                return None

    # async def on_message_delete(message):
    #     channel = client.get_channel('로그를 남길 채널의 id(int)')
    #     embed = discord.Embed(title=f"삭제됨", description=f"유저 : {message.author.mention} 채널 : {message.channel.mention}", color=0xFF0000)
    #     embed.add_field(name="삭제된 내용", value=f"내용 : {message.content}", inline=False)
    #     embed.set_footer(text=f"{message.guild.name} | {time}")
    #     await channel.send(embed=embed)

#봇 실행 함수
if __name__ == "__main__":
    client = chatbot()
    client.run(token[0])