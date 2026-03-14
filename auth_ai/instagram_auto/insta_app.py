import streamlit as st
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from instagrapi import Client
from PIL import Image

# --- 1. 환경 변수 로드 ---
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent / '.env'
load_dotenv(dotenv_path=env_path)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- 2. 로그인 로직 함수 (세션 관리 추가) ---
def get_insta_client():
    cl = Client()
    session_path = current_dir / "insta_session.json"

    username = os.getenv("INSTA_USER")
    password = os.getenv("INSTA_PW")

    # 세션 파일이 있으면 로드 시도
    if session_path.exists():
        try:
            cl.load_settings(session_path)
            cl.login(username, password)
            # 세션이 유효한지 간단한 체크
            cl.get_timeline_feed()
            st.sidebar.success("✅ 기존 세션으로 로그인되었습니다.")
        except Exception:
            # 세션이 만료되었거나 오류나면 새로 로그인
            st.sidebar.warning("⚠️ 세션이 만료되어 새로 로그인합니다.")
            cl.login(username, password)
            cl.dump_settings(session_path)
    else:
        # 세션 파일이 없으면 새로 로그인 후 저장
        cl.login(username, password)
        cl.dump_settings(session_path)
        st.sidebar.info("👋 첫 로그인: 세션 파일을 생성했습니다.")

    return cl


# --- 3. 페이지 설정 ---
st.set_page_config(page_title="인스타 슬라이드 업로더", page_icon="📸")
st.title("📸 AI 인스타 다중 업로더")

if "generated_caption" not in st.session_state:
    st.session_state.generated_caption = ""

# --- 4. 입력 섹션 ---
uploaded_files = st.file_uploader("이미지를 선택하세요 (최대 10장)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    if len(uploaded_files) > 10:
        st.error("최대 10장까지만 업로드 가능합니다.")
        uploaded_files = uploaded_files[:10]

    cols = st.columns(min(len(uploaded_files), 5))
    for idx, file in enumerate(uploaded_files):
        with cols[idx % 5]:
            st.image(file, caption=f"이미지 {idx + 1}", use_container_width=True)

user_topic = st.text_input("게시글의 주제를 입력하세요", placeholder="예: 제주도 여행 1일차 브이로그")

# --- 5. 1단계: 글 생성하기 ---
if st.button("📝 AI 글 생성하기"):
    if uploaded_files and user_topic:
        with st.spinner("Gemini가 콘텐츠 분석 중..."):
            try:
                first_img = Image.open(uploaded_files[0])
                prompt = f"""
                이 이미지들과 '{user_topic}' 주제로 만으로 인스타그램 게시글 본문을 작성해줘.
                
                [조건]
                1. 분량 : 250자 미만
                2. 해시태그 5~10개를 번호 없이 이어서 써줘
                3. 말투 : 친근한 블로그 어투 (~해요. ~했답니다.)
                4. 이모지 사용 : 문장 사이에 적절한 이모지 사용
                5. 마지막에 관련 해시태그 8~10개를 #태그명 형태로 나열해줘
                """

                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=[prompt, first_img]
                )
                st.session_state.generated_caption = response.text
            except Exception as e:
                st.error(f"글 생성 중 오류 발생: {e}")
    else:
        st.warning("이미지와 주제를 모두 입력해주세요.")

# --- 6. 2단계: 생성된 글 검토 및 수정 ---
if st.session_state.generated_caption:
    st.markdown("---")
    st.subheader("📝 생성된 글 검토")
    edited_caption = st.text_area("글 내용이 마음에 들지 않으면 수정하세요:",
                                  value=st.session_state.generated_caption,
                                  height=250)

    st.info("내용 확인 후 '최종 업로드 승인'을 눌러주세요.")

    # --- 7. 3단계: 최종 업로드 버튼 ---
    if st.button("🚀 최종 업로드 승인"):
        with st.spinner("인스타그램에 업로드 중 (IP 차단 주의)..."):
            try:
                temp_paths = []
                for idx, file in enumerate(uploaded_files):
                    img = Image.open(file).convert("RGB")
                    path = f"temp_{idx}.jpg"
                    img.save(path)
                    temp_paths.append(path)

                # 로그인 로직 호출
                cl = get_insta_client()

                # 앨범 업로드
                cl.album_upload(temp_paths, edited_caption)

                st.success("✅ 인스타그램에 성공적으로 업로드되었습니다!")

                # 파일 정리 및 세션 초기화
                for p in temp_paths:
                    if os.path.exists(p): os.remove(p)
                st.session_state.generated_caption = ""

            except Exception as e:
                st.error(f"업로드 실패: {e}")
                st.warning("팁: 폰의 핫스팟을 연결하여 IP를 바꾼 뒤 다시 시도해 보세요.")