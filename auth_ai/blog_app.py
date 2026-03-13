import streamlit as st
import os
from dotenv import load_dotenv
from PIL import Image
from openai import OpenAI
import google.generativeai as genai

# 1. 환경 변수 로드
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")


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
    # 모델 선택 메뉴
    model_choice = st.radio("사용할 AI 모델 선택", ["OpenAI", "Google Gemini"])

    st.divider()
    st.header("📌 기본 정보")
    category = st.selectbox("카테고리", ["맛집", "여행", "일상", "리뷰"])
    user_idea = st.text_area("글감 입력", placeholder="예: 강남역 데이트 맛집 후기")

# --- API 클라이언트 초기화 ---
client = None
gemini_model = None

if model_choice == "OpenAI":
    if openai_key:
        client = OpenAI(api_key=openai_key)
    else:
        st.error("OpenAI API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")
elif model_choice == "Google Gemini":
    if gemini_key:
        genai.configure(api_key=gemini_key)
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        st.error("Gemini API 키가 설정되지 않았습니다. .env 파일을 확인해주세요.")

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
            # 최신 문법인 use_container_width 사용
            st.image(thumb, use_container_width=True)
            tag_data[file.name] = st.selectbox(f"분류 {idx + 1} ({file.name})", tag_options, key=f"tag_{idx}")

# --- Step 2: 제목 생성 및 선택 ---
if user_idea and uploaded_files:
    st.divider()
    st.header("✍️ Step 2: 제목 추천받기")

    if st.button(f"🔎 {model_choice}로 제목 10개 추천받기"):
        with st.spinner("매력적인 제목을 생각 중입니다..."):
            title_prompt = f"주제 '{user_idea}'와 카테고리 '{category}'에 어울리는 블로그 제목 10개를 추천해줘. 클릭을 부르는 매력적인 문구여야 하며, 번호만 매겨서 나열해줘."

            response = gemini_model.generate_content(title_prompt)
            titles = response.text.split('\n')

            # 숫자와 공백 제거 후 리스트 저장
            st.session_state.suggested_titles = [t.strip() for t in titles if t.strip()]

    # 제목 리스트가 생성되었다면 선택창 보여주기
    if 'suggested_titles' in st.session_state:
        selected_title = st.selectbox("마음에 드는 제목을 골라주세요", st.session_state.suggested_titles)

        # --- Step 3: 본문 생성 ---
        st.header("📝 Step 3: 본문 생성")
        if st.button(f"🚀 '{selected_title}' 제목으로 글쓰기"):
            if (model_choice == "OpenAI" and client) or (
                    model_choice == "Google Gemini" and gemini_model):
                with st.spinner("본문을 작성 중입니다..."):
                    img_info = "\n".join([f"- {name}: {tag}" for name, tag in tag_data.items()])

                    # 본문 프롬프트에 선택한 제목 반영
                    prompt = f"""
                    블로그 본문을 작성해줘.
                    선택된 제목: {selected_title}
                    주제: {user_idea} (카테고리: {category})
                    이미지 리스트: {img_info}

                    [조건]
                    1. 제목은 반드시 '{selected_title}'를 사용할 것.
                    2. 분량: 1,500자 이상 상세한 본문.
                    3. 고정 인사말 : 방하! 오늘은 ~~~ 
                    4. 이미지 배치: 본문 중간중간 [IMAGE_파일명_태그]를 삽입할 것.
                    5. 말투: 친근한 블로그 어투 (~해요, ~했답니다).
                    6. 이모지 사용: 문장 사이에 적절한 이모지를 풍부하게 넣어줘.
                    7. 고정 클로징 : 함바! ~~~
                    8. 마지막에 관련 해시태그 20개를 #태그명 형태로 나열해줘.
                    """

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

    # 결과 출력 (동일)
    if 'final_blog' in st.session_state:
        st.subheader("✅ 최종 완성본")
        st.text_area("결과 복사", st.session_state.final_blog, height=600)
        st.download_button("텍스트 파일 저장", st.session_state.final_blog, file_name="ai_blog_post.txt")