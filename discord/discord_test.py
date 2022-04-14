import discord
import os

token_path = os.path.dirname(os.path.abspath(__file__))+"/token.txt"
t = open(token_path, "r", encoding="utf-8")
token = t.read().split()[0]

#봇 메인 함수
class chatbot(discord.Client):
    async def on_rady(self):
        game = discord.Game("내용")
        await client.change_presence(status=discord.Status.online, activity=game)
        print("READY")

    async def on_message(self, message):
        # 상대가 bot일 경우 응답하지 않음
        if message.author.bot:
            return None

        if message.content == "!help":
            channel = message.channel
            msg = "안녕하세요. 김경하가 만든 테스트 봇입니다."
            await channel.send(msg)
            return None

#봇 실행 함수
if __name__ == "__main__":
    client = chatbot()
    client.run(token)