import streamlit as st
import os
from dotenv import load_dotenv
from PIL import Image
from openai import OpenAI
#import google.generativeai as genai

# 환경 변수 로드
load_dotenv()


def resize_image(uploaded_file, size=(300, 300)):
    image = Image.open(uploaded_file)
    image.thumbnail(size)
    return image


# 페이지 설정
st.set_page_config(page_title="AI 블로그 포스팅기", layout="wide")
st.title("🤖 블로그 자동화: GPT vs Gemini")

# --- 사이드바: 모델 및 설정 ---
with st.sidebar:
    st.header("⚙️ 모델 설정")
    # 모델 선택 메뉴
    model_choice = st.radio("사용할 AI 모델 선택", ["OpenAI GPT-4o", "Google Gemini 1.5 Pro"])

    st.divider()
    st.header("📌 기본 정보")
    category = st.selectbox("카테고리", ["맛집", "여행", "일상", "리뷰"])
    user_idea = st.text_area("글감 입력", placeholder="예: 강남역 데이트 맛집 후기")

# --- API 클라이언트 초기화 ---
if model_choice == "OpenAI GPT-4o":
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# elif model_choice == "Google Gemini 1.5 Pro":
#     genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
#     gemini_model = genai.GenerativeModel('gemini-1.5-pro')

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
            st.image(thumb, use_column_width=True)
            tag_data[file.name] = st.selectbox(f"분류 {idx + 1}", tag_options, key=f"tag_{idx}")

# --- Step 2: 제목 및 본문 생성 ---
if user_idea and uploaded_files:
    st.divider()

    # 1. 제목 생성 로직
    if st.button(f"✨ {model_choice}로 제목/본문 생성"):
        with st.spinner(f"{model_choice}가 글을 쓰고 있습니다..."):

            img_info = "\n".join([f"- {name}: {tag}" for name, tag in tag_data.items()])
            prompt = f"""
            제목과 본문을 작성해줘.
            주제: {user_idea} (카테고리: {category})
            이미지 리스트: {img_info}

            [조건]
            1. 제목: 네이버 블로그 최적화 제목 1개.
            2. 본문: 1,500자 이상, 친근한 말투, 이모지 활용.
            3. 본문 중간에 [IMAGE_파일명_태그] 삽입.
            4. 마지막에 해시태그 20개 포함.
            """

            # 모델별 호출 방식 분기
            if model_choice == "OpenAI GPT-4o":
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}]
                )
                final_text = response.choices[0].message.content
            else:
                response = gemini_model.generate_content(prompt)
                final_text = response.text

            st.session_state.final_blog = final_text

    # 결과 출력
    if 'final_blog' in st.session_state:
        st.subheader("✅ 생성 결과")
        st.text_area("결과 복사", st.session_state.final_blog, height=600)
        st.download_button("텍스트 파일 저장", st.session_state.final_blog, file_name="ai_blog_post.txt")