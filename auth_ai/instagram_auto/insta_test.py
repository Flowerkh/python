import os
import requests
import time
from dotenv import load_dotenv
from pathlib import Path

# 1. 상위 폴더의 .env 파일 로드
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# 환경 변수 가져오기
ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
IG_ID = os.getenv("IG_ID")

def post_carousel_to_ig(image_urls, caption, access_token, ig_user_id):
    if not access_token or not ig_user_id:
        print("❌ 에러: 토큰 또는 IG_ID가 설정되지 않았습니다. .env 파일을 확인하세요.")
        return

    item_ids = []

    # 1단계: 개별 이미지 컨테이너 ID 생성
    print("📸 1단계: 개별 이미지 등록 시작...")
    for url in image_urls:
        url_items = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
        payload = {
            'image_url': url,
            'is_carousel_item': 'true',
            'access_token': access_token
        }
        res = requests.post(url_items, data=payload).json()

        if 'id' in res:
            item_ids.append(res['id'])
            print(f"✅ 이미지 등록 성공 (ID: {res['id']})")
        else:
            print(f"❌ 이미지 등록 실패: {res}")
            return res

    # 2단계: 이미지들을 하나로 묶는 캐러셀 컨테이너 생성
    print("\n📦 2단계: 캐러셀 묶음(Carousel Container) 생성 중...")
    url_carousel = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    payload_carousel = {
        'media_type': 'CAROUSEL',
        'children': ",".join(item_ids),
        'caption': caption,
        'access_token': access_token
    }
    res_carousel = requests.post(url_carousel, data=payload_carousel).json()

    if 'id' in res_carousel:
        carousel_container_id = res_carousel['id']
        print(f"✅ 캐러셀 묶음 생성 성공 (ID: {carousel_container_id})")

        # ⚠️ 중요: 인스타그램 서버가 이미지를 처리할 시간을 주어야 합니다.
        print("⏳ 서버 처리 대기 중 (10초)...")
        time.sleep(10)

        # 3단계: 최종 게시물 발행
        print("🚀 3단계: 인스타그램에 게시물 발행!")
        url_publish = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
        payload_publish = {
            'creation_id': carousel_container_id,
            'access_token': access_token
        }
        final_res = requests.post(url_publish, data=payload_publish).json()
        return final_res
    else:
        print(f"❌ 캐러셀 생성 실패: {res_carousel}")
        return res_carousel

if __name__ == "__main__":
    # .jpg, .png 등으로 끝나는 직통 링크인지 꼭 확인하세요!
    IMAGES = [
        "https://picsum.photos/id/10/800/800.jpg",
        "https://picsum.photos/id/20/800/800.jpg",
        "https://picsum.photos/id/30/800/800.jpg"
    ]

    TEXT = "함하! 🤖\n여수 벚꽃 3종 세트 미리 보기! 🌸\n#여수 #벚꽃 #파이썬독학 #함바"

    result = post_carousel_to_ig(IMAGES, TEXT, ACCESS_TOKEN, IG_ID)

    if result and 'id' in result:
        print("\n🎉 인스타그램 업로드 성공!")
        print(f"게시물 ID: {result['id']}")
    else:
        print("\n😱 업로드 실패...")
        print(f"상세 에러: {result}")