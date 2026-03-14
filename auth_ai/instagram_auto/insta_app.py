import streamlit as st
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from instagrapi import Client
from PIL import Image
import tempfile

# --- 1. 설정 로드 ---
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent / '.env'
load_dotenv(dotenv_path=env_path)

USERNAME = os.getenv("INSTA_USERNAME")
PASSWORD = os.getenv("INSTA_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. Streamlit UI ---
st.set_page_config(page_title="인스타 릴스 업로더", page_icon="🎬")
st.title("🎬 인스타 릴스 업로더")

if "generated_caption" not in st.session_state:
    st.session_state.generated_caption = ""

# 비디오 파일을 받도록 수정 (mp4, mov 등)
uploaded_video = st.file_uploader("업로드할 릴스 영상을 선택하세요", type=["mp4", "mov", "avi"])
user_topic = st.text_input("게시글 주제 (예: 12지신 애니메이션)")

# --- 3. Gemini 본문 생성 ---
if st.button("📝 AI 본문 생성"):
    if uploaded_video and user_topic:
        with st.spinner("AI가 영상을 분석하고 글을 쓰고 있습니다..."):
            try:
                # 영상 파일의 경우 첫 프레임을 추출하거나 주제만으로 생성할 수 있습니다.
                # 여기서는 주제를 중심으로 본문을 작성하도록 설정했습니다.
                prompt = f"""
                '{user_topic}' 주제의 인스타그램 릴스 게시글 본문을 작성해줘.

                [조건]
                1. 분량 : 250자 미만
                2. 해시태그 8~10개를 번호 없이 이어서 써줘
                3. 말투 : 친근한 블로그 어투 (~해요. ~했답니다.)
                4. 이모지 사용 : 문장 사이에 적절한 이모지 사용
                """
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=[prompt]
                )
                st.session_state.generated_caption = response.text
            except Exception as e:
                st.error(f"본문 생성 실패: {e}")

# --- 4. 릴스 업로드 로직 ---
if st.session_state.generated_caption:
    caption = st.text_area("내용 수정", value=st.session_state.generated_caption, height=150)

    if st.button("🚀 릴스 업로드"):
        with st.spinner("릴스 업로드 중..."):
            cl = Client()

            # 임시 파일 경로 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                tmp.write(uploaded_video.read())
                video_path = tmp.name

            try:
                # 로그인
                cl.login(USERNAME, PASSWORD)
                st.sidebar.write(f"로그인 성공! ID: {cl.user_id}")

                # 보안을 위한 대기
                time.sleep(3)

                # 릴스 업로드 (clip_upload 사용)
                # 영상 파일과 캡션만 넣으면 자동으로 릴스로 업로드됩니다.
                cl.clip_upload(video_path, caption)

                st.success("✅ 릴스 업로드에 성공했습니다!")
                st.balloons()

            except Exception as e:
                st.error(f"업로드 에러 발생: {e}")
            finally:
                # 임시 비디오 파일 삭제
                if os.path.exists(video_path):
                    os.remove(video_path)