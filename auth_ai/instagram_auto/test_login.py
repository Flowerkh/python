import os
import pyotp
from pathlib import Path
from dotenv import load_dotenv
from instagrapi import Client

# 1. 환경 변수 로드
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent / '.env'
load_dotenv(dotenv_path=env_path)
def test_insta_login():
    cl = Client()

    # 환경 변수 가져오기
    username = os.getenv("INSTA_USER")
    password = os.getenv("INSTA_PW")
    two_fa_seed = os.getenv("INSTA_2FA_SEED")

    print(f"🔍 로그인 시도 중: {username}")

    try:
        # 일단 아이디/비번으로 시도
        try:
            cl.login(username, password)
            print("✅ 1단계 로그인 성공 (2FA 불필요)")
        except Exception as e:
            if "two_factor_required" in str(e).lower():
                print("🔑 2단계 인증(2FA)이 필요합니다. 코드를 생성합니다...")

                # OTP 번호 생성
                totp = pyotp.TOTP(two_fa_seed.replace(" ", ""))
                otp_code = totp.now()
                print(f"🔢 생성된 OTP 번호: {otp_code}")

                # OTP 코드로 다시 로그인
                cl.login(username, password, verification_code=otp_code)
                print("✅ 2단계 인증으로 로그인 성공!")
            else:
                raise e

        # 로그인 성공 후 계정 정보 살짝 확인
        user_info = cl.user_info(cl.user_id)
        print(f"✨ 로그인 된 계정 이름: {user_info.full_name}")
        print(f"📊 팔로워 수: {user_info.follower_count}")
        print("\n🎉 모든 관문을 통과했습니다! 이제 업로드 도구를 사용하셔도 됩니다.")

    except Exception as e:
        print("\n❌ 로그인 실패")
        print(f"오류 내용: {e}")

        if "checkpoint_required" in str(e).lower():
            print("💡 조치: 인스타 앱에서 '본인이 맞음'을 눌러주세요.")
        elif "blacklist" in str(e).lower():
            print("💡 조치: IP가 차단되었습니다. 폰 핫스팟/테더링을 연결하세요.")


if __name__ == "__main__":
    test_insta_login()