import streamlit as st
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from instagrapi import Client
from PIL import Image

# --- 1. 설정 로드 ---
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent / '.env'
load_dotenv(dotenv_path=env_path)

# .env에서 정보 가져오기
USERNAME = os.getenv("INSTA_USERNAME")
PASSWORD = os.getenv("INSTA_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)


# --- 2. 이미지 가공 함수 (성공하신 코드의 경로 처리를 위해 유지) ---
def process_insta_image(input_file, output_path):
    with Image.open(input_file) as img:
        img = img.convert("RGB")
        # 인스타그램 권장 사이즈
        img.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
        new_img = Image.new("RGB", (1080, 1080), (255, 255, 255))
        offset = ((1080 - img.size[0]) // 2, (1080 - img.size[1]) // 2)
        new_img.paste(img, offset)
        # 메타데이터 제거 및 최적화 저장
        new_img.save(output_path, "JPEG", quality=90, optimize=True)


# --- 3. Streamlit UI ---
st.set_page_config(page_title="인스타 업로더", page_icon="📸")
st.title("📸 인스타 업로더")

if "generated_caption" not in st.session_state:
    st.session_state.generated_caption = ""

# 사진 한 장만 받도록 설정
uploaded_file = st.file_uploader("업로드할 사진을 선택하세요", type=["jpg", "jpeg", "png"])
user_topic = st.text_input("게시글 주제 (예: 주말 나들이)")

# --- 4. Gemini 본문 생성 ---
if st.button("📝 AI 본문 생성"):
    if uploaded_file and user_topic:
        with st.spinner("AI가 글을 쓰고 있습니다..."):
            try:
                img_for_ai = Image.open(uploaded_file)
                prompt =  f"""
                이 이미지들과 '{user_topic}' 주제로 만으로 인스타그램 게시글 본문을 작성해줘.
                
                [조건]
                1. 분량 : 250자 미만
                2. 해시태그 8~10개를 번호 없이 이어서 써줘
                3. 말투 : 친근한 블로그 어투 (~해요. ~했답니다.)
                4. 이모지 사용 : 문장 사이에 적절한 이모지 사용
                """
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=[prompt, img_for_ai]
                )
                st.session_state.generated_caption = response.text
            except Exception as e:
                st.error(f"본문 생성 실패: {e}")

# --- 5. 최종 업로드 로직 (성공한 코드 로직 반영) ---
if st.session_state.generated_caption:
    caption = st.text_area("내용 수정", value=st.session_state.generated_caption, height=150)

    if st.button("🚀 인스타그램에 업로드"):
        with st.spinner("업로드 중..."):
            cl = Client()
            temp_path = str(current_dir / "upload_ready.jpg")

            try:
                # 1. 이미지 가공
                process_insta_image(uploaded_file, temp_path)

                # 2. 로그인 (성공하신 방식 그대로)
                cl.login(USERNAME, PASSWORD)
                st.sidebar.write(f"로그인 성공! ID: {cl.user_id}")

                # 3. 약간의 대기 (보안 방지)
                time.sleep(2)

                # 4. 업로드 실행
                cl.photo_upload(temp_path, caption)

                st.success("✅ 업로드에 성공했습니다!")
                st.balloons()

            except Exception as e:
                st.error(f"업로드 에러 발생: {e}")
            finally:
                # 임시 파일 삭제
                if os.path.exists(temp_path):
                    os.remove(temp_path)