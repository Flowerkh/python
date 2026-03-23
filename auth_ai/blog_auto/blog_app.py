import streamlit as st
from PIL import Image
from pathlib import Path
import sys

# 1. 공용 모듈 경로 추가 (ai_utils.py를 찾기 위함)
# blog_app.py가 하위 폴더에 있다면 상위 폴더를 경로에 추가해야 합니다.
current_file = Path(__file__).resolve()
auth_ai_dir = current_file.parent.parent  # auth_ai 폴더 경로
if str(auth_ai_dir) not in sys.path:
    sys.path.append(str(auth_ai_dir))

# 공용 모듈에서 AI 클라이언트 가져오기
from ai_utils import get_ai_client


def resize_image(uploaded_file, size=(300, 300)):
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
    category = st.selectbox("카테고리", ["맛집", "여행", "일상", "리뷰"])
    user_idea = st.text_area("글감 입력", placeholder="예: 강남역 데이트 맛집 후기")

# --- API 클라이언트 초기화 (공용 모듈 사용) ---
# ai_utils.py에서 클라이언트를 가져옵니다.
ai_instance, error_msg = get_ai_client(model_choice)

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
    tag_options = ["선택안함", "외관", "실내", "메뉴판", "메인음식", "상세컷"]
    for idx, file in enumerate(uploaded_files):
        with cols[idx % 3]:
            thumb = resize_image(file)
            st.image(thumb, use_container_width=True)
            tag_data[file.name] = st.selectbox(f"분류 {idx + 1} ({file.name})", tag_options, key=f"tag_{idx}")

# --- Step 2: 제목 생성 및 선택 ---
if user_idea and uploaded_files:
    st.divider()
    st.header("✍️ Step 2: 제목 추천받기")

    if st.button(f"🔎 {model_choice}로 제목 10개 추천받기"):
        if not ai_instance:
            st.warning("AI 클라이언트가 초기화되지 않았습니다.")
        else:
            with st.spinner("매력적인 제목을 생각 중입니다..."):
                title_prompt = f"주제 '{user_idea}'와 카테고리 '{category}'에 어울리는 블로그 제목 10개를 추천해줘. 클릭을 부르는 매력적인 문구여야 하며, 번호만 매겨서 나열해줘."

                try:
                    if model_choice == "OpenAI":
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": title_prompt}]
                        )
                        titles_text = response.choices[0].message.content
                    else:
                        response = gemini_model.generate_content(title_prompt)
                        titles_text = response.text

                    titles = titles_text.split('\n')
                    st.session_state.suggested_titles = [t.strip() for t in titles if t.strip()]
                except Exception as e:
                    st.error(f"제목 생성 중 오류 발생: {e}")

    if 'suggested_titles' in st.session_state:
        selected_title = st.selectbox("마음에 드는 제목을 골라주세요", st.session_state.suggested_titles)

        # --- Step 3: 본문 생성 ---
        st.header("📝 Step 3: 본문 생성")
        if st.button(f"🚀 '{selected_title}' 제목으로 글쓰기"):
            with st.spinner("본문을 작성 중입니다..."):
                img_info = "\n".join([f"- {name}: {tag}" for name, tag in tag_data.items()])
                prompt = f"""
                블로그 본문을 작성해줘.
                선택된 제목: {selected_title}
                주제: {user_idea} (카테고리: {category})
                이미지 리스트: {img_info}

                [조건]
                1. 제목은 반드시 '{selected_title}'를 사용할 것.
                2. 분량: 1,500자 이상 상세한 본문.
                3. 고정 인사말 : 함하! 오늘은 ~~~ 
                4. 이미지 배치: 본문 중간중간 [IMAGE_파일명_태그]를 삽입할 것.
                5. 말투: 친근한 블로그 어투 (~해요, ~했답니다).
                6. 이모지 사용: 문장 사이에 적절한 이모지를 풍부하게 넣어줘.
                7. 고정 클로징 : 함바! ~~~
                8. 마지막에 관련 해시태그 20개를 #태그명 형태로 나열해줘(공백 제거).
                """

                try:
                    if model_choice == "OpenAI":
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        final_text = response.choices[0].message.content
                    else:
                        response = gemini_model.generate_content(prompt)
                        final_text = response.text

                    st.session_state.final_blog = final_text
                except Exception as e:
                    st.error(f"본문 생성 중 오류 발생: {e}")

    if 'final_blog' in st.session_state:
        st.subheader("✅ 최종 완성본")
        st.text_area("결과 복사", st.session_state.final_blog, height=600)
        st.download_button("텍스트 파일 저장", st.session_state.final_blog, file_name="ai_blog_post.txt")