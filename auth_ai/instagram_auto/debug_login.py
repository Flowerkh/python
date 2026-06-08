import time
from instagrapi import Client

cl = Client()
USERNAME = "instagram_id"
PASSWORD = "instagram_pw"

try:
    cl.login(USERNAME, PASSWORD)
    print("로그인 성공!")

    # 에러가 발생하는 user_info 대신, 아주 기본적인 ID만 출력해봅니다.
    print(f"내 계정 숫자 ID: {cl.user_id}")

    cl.photo_upload("./20260314_114049.jpg", "로그인 성공 기념 업로드!")

except Exception as e:
    # 에러가 나더라도 'pinned_channels_info' 관련이면 무시하고 진행 가능합니다.
    print(f"오류 발생: {e}")