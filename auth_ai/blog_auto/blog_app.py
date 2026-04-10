import textwrap
import streamlit as st
from PIL import Image
import sys
from pathlib import Path

# 1. 현재 파일(blog_app.py)의 부모의 부모 폴더(auth_ai) 경로를 계산합니다.
# .parent는 blog_auto, .parent.parent는 auth_ai 폴더가 됩니다.
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from ai_utils import get_ai_client, generate_text

CATEGORY_TAGS = {
    "맛집": ["선택안함", "외관/간판", "실내/인테리어", "메뉴판", "메인음식", "상세컷(음식)", "영수증/지도"],
    "여행": ["선택안함", "풍경/전경", "숙소/실내", "이동수단(비행기/기차)", "티켓/안내판", "활동(액티비티)", "현지음식"],
    "일상": ["선택안함", "오늘의무드", "소품/구매템", "셀카/인물", "풍경", "반려동물/식물", "기타"],
    "IT/리뷰": ["선택안함", "제품박스", "제품외관", "상세디테일", "실제사용기", "설정화면/UI", "비교샷"]
}

def resize_image(uploaded_file, size=(150, 150)):
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    image.thumbnail(size)
    return image


# 페이지 설정
st.set_page_config(page_title="AI 블로그 포스팅기", layout="wide")
st.title("🤖 블로그 자동화")

# --- 사이드바: 모델 및 설정 ---
with st.sidebar:
    st.header("⚙️ 모델 설정")
    model_choice = st.radio("사용할 AI 모델 선택", ["OpenAI", "Google Gemini"])

    st.divider()
    st.header("📌 기본 정보")
    category = st.selectbox("카테고리", list(CATEGORY_TAGS.keys()))
    tag_options = CATEGORY_TAGS.get(category, CATEGORY_TAGS["일상"])
    user_idea = st.text_area("글감 입력", placeholder="예: 강남역 데이트 맛집 후기")

# --- API 클라이언트 초기화 (공용 모듈 사용) ---
@st.cache_resource
def load_ai_client(model_choice):
    return get_ai_client(model_choice)

ai_instance, error_msg = load_ai_client(model_choice)

client = None
gemini_model = None

if error_msg:
    st.error(error_msg)
else:
    if model_choice == "OpenAI":
        client = ai_instance
    else:
        gemini_model = ai_instance

# --- Step 1: 이미지 업로드 ---
st.header("🖼️ 이미지 업로드")
uploaded_files = st.file_uploader("사진을 올려주세요", accept_multiple_files=True, type=['jpg', 'png', 'jpeg'])

tag_data = {}
if uploaded_files:
    cols = st.columns(3)
    for idx, file in enumerate(uploaded_files):
        with cols[idx % 3]:
            thumb = resize_image(file)
            st.image(thumb, use_container_width=True)
            # 위에서 설정한 tag_options가 여기서 사용됩니다.
            tag_data[file.name] = st.selectbox(
                f"분류 {idx + 1}",
                tag_options,
                key=f"tag_{idx}"
            )

# --- Step 2: 제목 생성 및 선택 ---
if user_idea and uploaded_files:
    st.divider()
    st.header("✍️ Step 2: 제목 추천받기")

    if st.button(f"🔎 {model_choice}로 제목 10개 추천받기"):
        if error_msg:
            st.warning("AI 클라이언트가 초기화되지 않았습니다. 사이드바의 오류를 확인해주세요.")
        else:
            with st.spinner("매력적인 제목을 생각 중입니다..."):
                title_prompt = f"주제 '{user_idea}'와 카테고리 '{category}'에 어울리는 블로그 제목 10개를 추천해줘. 클릭을 부르는 매력적인 문구여야 하며, 번호만 매겨서 나열해줘."

                try:
                    titles_text = generate_text(model_choice, client, gemini_model, title_prompt)
                    st.session_state.suggested_titles = [t.strip() for t in titles_text.split('\n') if t.strip()]
                except Exception as e:
                    st.error(f"제목 생성 중 오류 발생: {e}")

    if 'suggested_titles' in st.session_state:
        selected_title = st.selectbox("마음에 드는 제목을 골라주세요", st.session_state.suggested_titles)

        # --- Step 3: 본문 생성 ---
        st.header("📝 Step 3: 본문 생성")
        if st.button(f"🚀 '{selected_title}' 제목으로 글쓰기"):
            with st.spinner("본문을 작성 중입니다..."):
                img_info = "\n".join([f"- {name}: {tag}" for name, tag in tag_data.items()])
                prompt = textwrap.dedent(f"""
                    블로그 본문을 작성해줘.
                    각 이미지의 태그 정보를 바탕으로, 해당 사진이 글의 흐름상 자연스러운 위치에 오도록 배치해줘. 예를 들어 '외관' 태그는 글의 초반부에, '메인음식'은 중간 상세 설명 부분에 언급해줘.
                    선택된 제목: {selected_title}
                    주제: {user_idea} (카테고리: {category})
                    이미지 리스트: {img_info}

                    [조건]
                    1. 제목은 반드시 '{selected_title}'를 사용할 것.
                    2. 분량: 1,500자 이상 상세한 본문.
                    3. 고정 인사말 : 함하! 오늘은 ~~~
                    4. 이미지 배치: 본문 중간중간 [IMAGE_파일명_태그]를 삽입할 것.
                    5. 말투: 친근한 블로그 어투 (~해요, ~했답니다).
                    6. 이모지 사용 금지.
                    7. 고정 클로징 : 함바! ~~~
                    8. 마지막에 관련 해시태그 20~30개를 #태그명 형태로 나열해줘(공백 제거).
                """).strip()

                try:
                    st.session_state.final_blog = generate_text(model_choice, client, gemini_model, prompt)
                except Exception as e:
                    st.error(f"본문 생성 중 오류 발생: {e}")

    if 'final_blog' in st.session_state:
        st.subheader("✅ 최종 완성본")
        st.text_area("결과 복사", st.session_state.final_blog, height=600)
        st.download_button("텍스트 파일 저장", st.session_state.final_blog, file_name="ai_blog_post.txt")