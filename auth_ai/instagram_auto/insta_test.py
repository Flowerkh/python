import os
import requests
import time
import json
from dotenv import load_dotenv
from pathlib import Path

# 1. .env 파일 로드 및 환경 변수 설정
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
IG_ID = os.getenv("IG_ID")


def post_to_ig(image_urls, caption, access_token, ig_user_id):
    if not access_token or not ig_user_id:
        print("❌ 에러: 토큰 또는 IG_ID가 설정되지 않았습니다.")
        return

    count = len(image_urls)
    creation_id = None

    # --- [경우 1] 이미지 1장일 때 (단일 이미지 포스팅) ---
    if count == 1:
        print("📸 1장 모드: 단일 이미지 컨테이너 생성 중...")
        url = f"https://graph.instagram.com/v19.0/{ig_user_id}/media"
        payload = {
            'image_url': image_urls[0],
            'caption': caption,
            'access_token': access_token
        }
        res = requests.post(url, data=payload).json()

        if 'id' in res:
            creation_id = res['id']
            print(f"✅ 단일 이미지 컨테이너 성공 (ID: {creation_id})")
        else:
            print(f"❌ 단일 이미지 생성 실패: {res}")
            return res

    # --- [경우 2] 이미지 2장 이상일 때 (캐러셀 포스팅) ---
    else:
        print(f"📦 {count}장 캐러셀 모드: 묶음 작업 시작...")
        item_ids = []

        # 2-1단계: 개별 이미지 아이템 등록
        for idx, url in enumerate(image_urls):
            print(f"   - 이미지 ({idx + 1}/{count}) 등록 중...")
            url_item = f"https://graph.instagram.com/v19.0/{ig_user_id}/media"
            payload_item = {
                'image_url': url,
                'is_carousel_item': 'true',
                'access_token': access_token
            }
            res_item = requests.post(url_item, data=payload_item).json()

            if 'id' in res_item:
                item_ids.append(res_item['id'])
                time.sleep(3)  # 인스타그램 서버 다운로드 대기 시간
            else:
                print(f"❌ 이미지 {idx + 1} 등록 실패: {res_item}")
                return res_item

        # 2-2단계: 캐러셀 부모 컨테이너 생성 (ID들을 하나로 묶기)
        print("   - 캐러셀 묶음(Parent) 생성 중...")
        url_carousel = f"https://graph.instagram.com/v19.0/{ig_user_id}/media"

        # ⚠️ 중요: children은 JSON 배열 문자열 형식이어야 합니다. ["ID1", "ID2"]
        payload_carousel = {
            'media_type': 'CAROUSEL',
            'children': json.dumps(item_ids),
            'caption': caption,
            'access_token': access_token
        }
        res_carousel = requests.post(url_carousel, data=payload_carousel).json()

        if 'id' in res_carousel:
            creation_id = res_carousel['id']
            print(f"✅ 캐러셀 묶음 생성 성공 (ID: {creation_id})")
        else:
            print(f"❌ 캐러셀 생성 실패: {res_carousel}")
            return res_carousel

    # --- [공통] 최종 단계: 게시물 발행 (Publish) ---
    if creation_id:
        print("⏳ 최종 발행 전 서버 처리 대기 (10초)...")
        time.sleep(10)

        print("🚀 인스타그램에 게시물 발행!")
        url_publish = f"https://graph.instagram.com/v19.0/{ig_user_id}/media_publish"
        payload_publish = {
            'creation_id': creation_id,
            'access_token': access_token
        }
        final_res = requests.post(url_publish, data=payload_publish).json()
        return final_res


if __name__ == "__main__":
    # 테스트용 이미지 (2장 이상이면 캐러셀, 1장이면 단일 포스팅)
    TEST_IMAGES = [
        "https://cdn.pixabay.com/photo/2015/04/23/22/00/tree-736885_1280.jpg",
        "https://cdn.pixabay.com/photo/2016/05/05/02/37/sunset-1373171_1280.jpg",
        "https://cdn.pixabay.com/photo/2017/02/08/17/24/fantasy-2049567_1280.jpg"
    ]

    CAPTION = "위스키 다이어리 자동 업로드 테스트 🥃\n#위스키 #파이썬 #자동화 #성공"

    result = post_to_ig(TEST_IMAGES, CAPTION, ACCESS_TOKEN, IG_ID)

    if result and 'id' in result:
        print(f"\n🎉 업로드 대성공! 게시물 ID: {result['id']}")
    else:
        print(f"\n😱 업로드 실패: {result}")