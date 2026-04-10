import textwrap
import streamlit as st
import os
import sys
import time
from pathlib import Path
from google import genai
from instagrapi import Client
from PIL import Image
import tempfile

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from ai_utils import load_ai_keys

# --- 1. 설정 로드 ---
keys = load_ai_keys()
USERNAME = os.getenv("INSTA_USERNAME")
PASSWORD = os.getenv("INSTA_PASSWORD")

SESSION_FILE = Path(__file__).resolve().parent / "insta_session.json"

@st.cache_resource
def get_gemini_client():
    if not keys["gemini"]:
        raise ValueError("GEMINI_API_KEY가 없습니다. .env 파일을 확인해주세요.")
    return genai.Client(api_key=keys["gemini"])

@st.cache_resource
def get_insta_client():
    cl = Client()
    if SESSION_FILE.exists():
        cl.load_settings(SESSION_FILE)
        cl.login(USERNAME, PASSWORD)
    else:
        cl.login(USERNAME, PASSWORD)
        cl.dump_settings(SESSION_FILE)
    return cl

client = get_gemini_client()

# --- 2. Streamlit UI ---
st.set_page_config(page_title="인스타 릴스 업로더", page_icon="🎬")
st.title("🎬 인스타 릴스 업로더")

if "generated_caption" not in st.session_state:
    st.session_state.generated_caption = ""

uploaded_video = st.file_uploader("업로드할 릴스 영상을 선택하세요", type=["mp4", "mov", "avi"])
user_topic = st.text_input("게시글 주제 (예: 12지신 애니메이션)")

# --- 3. Gemini 본문 생성 ---
if st.button("📝 AI 본문 생성"):
    if uploaded_video and user_topic:
        with st.spinner("AI가 영상을 분석하고 글을 쓰고 있습니다..."):
            try:
                prompt = textwrap.dedent(f"""
                    '{user_topic}' 주제의 인스타그램 릴스 게시글 본문을 작성해줘.

                    [조건]
                    1. 분량 : 250자 미만
                    2. 해시태그 8~10개를 번호 없이 이어서 써줘
                    3. 말투 : 친근한 블로그 어투 (~해요. ~했답니다.)
                    4. 이모지 사용 : 문장 사이에 적절한 이모지 사용
                """).strip()
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
        if not uploaded_video:
            st.warning("업로드할 영상을 먼저 선택해주세요.")
        else:
            with st.spinner("릴스 업로드 중..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                    tmp.write(uploaded_video.read())
                    video_path = tmp.name

                try:
                    cl = get_insta_client()
                    st.sidebar.write(f"로그인 성공! ID: {cl.user_id}")

                    time.sleep(3)

                    cl.clip_upload(video_path, caption)

                    st.success("✅ 릴스 업로드에 성공했습니다!")
                    st.balloons()

                except Exception as e:
                    st.error(f"업로드 에러 발생: {e}")
                finally:
                    if os.path.exists(video_path):
                        os.remove(video_path)