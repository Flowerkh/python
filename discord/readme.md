# DISCORD 갱하봇
### 개발 환경
```
OS : Windows10
Python : Python 3.9.10 (최소 3.5 이상 버전 사용해야 함)
IDE : jetbrain Pycharm 
```
### 디스코드 API 문서
https://discordpy.readthedocs.io/en/latest/index.html

### 봇 생성
1. https://discord.com/developers/applications/
2. 디스코드 개발자 포털 > 로그인
3. New Application 봇 생성
4. Bot > Token 생성 Copy -> token.txt 파일 생성하여 경로에 넣기

token.txt
```
key
discord id (int)
```

Status
>discord.status.online: 온라인 상태로 설정합니다.<br/>
discord.status.offline: 오프라인 상태로 설정합니다.<br/>
discord.status.idle: 자리 비움 상태로 정의합니다.<br/>
discord.status.dnd: 방해 금지 모드로 설정합니다. (빨간색 - 표시)<br/>
discord.status.invisible: 오프라인 상태로 보이게 합니다. (= discord.status.offline)

activity
>discord.Game: 게임 하는 중으로 정의합니다.<br/>
discord.Streaming: 방송 하는 중으로 정의합니다. 여기서 제목과 URL 값이 파라미터로 들어갑니다. URL은 트위치 URL이어야합니다.<br/>
discord.CustomActivity: 현재 봇에서는 미지원 상태입니다.<br/>
discord.Activity: 봇이 활동을 하고 있다고 정의합니다. 여기선 음악 듣는 중, 영상 보는 중이 이에 들어갑니다.

기능
> 메세지 청소 기능
> 메세지 채팅 로그 저장
> 로스트아크 게임 캐릭터 정보 불러오기
