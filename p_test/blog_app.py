import streamlit as st
from openai import OpenAI
from PIL import Image
import io

# 1. OpenAI 클라이언트 설정 (본인의 API 키 입력)
client = OpenAI(api_key="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")


def resize_image(uploaded_file, size=(300, 300)):
    """이미지를 썸네일 크기로 축소하여 메모리 부담을 줄임"""
    image = Image.open(uploaded_file)
    image.thumbnail(size)
    return image


# 앱 페이지 설정 (구버전 호환성 유지)
st.set_page_config(page_title="고속 블로그 작성기", layout="wide")
st.title("🚀 이미지 최적화 블로그 자동화")

# --- 세션 상태 초기화 ---
if 'titles' not in st.session_state:
    st.session_state.titles = []
if 'selected_title' not in st.session_state:
    st.session_state.selected_title = ""

# --- Step 1 & 2: 정보 입력 ---
with st.sidebar:
    st.header("📌 기본 설정")
    category = st.selectbox("카테고리", ["맛집", "여행", "일상", "리뷰"])
    user_idea = st.text_area("글감 (50자 미만)", placeholder="예: 강남역 새로 생긴 돈까스 맛집 육즙이 대박임")

# --- Step 3: 이미지 업로드 및 최적화 ---
st.header("🖼️ 이미지 업로드 및 태깅")
uploaded_files = st.file_uploader("이미지 10~30장을 업로드하세요", accept_multiple_files=True, type=['jpg', 'png', 'jpeg'])

tag_data = {}

if uploaded_files:
    num_files = len(uploaded_files)
    st.info(f"현재 {num_files}장의 이미지가 감지되었습니다.")

    # 3열 그리드로 이미지 표시
    cols = st.columns(3)
    tag_options = ["선택안함", "외관", "실내", "메뉴판", "메인음식", "상세컷", "풍경", "지도/정보"]

    for idx, file in enumerate(uploaded_files):
        with cols[idx % 3]:
            # [최적화] 썸네일 생성
            thumb = resize_image(file)
            # [수정] use_container_width 대신 구버전 옵션인 use_column_width 사용
            st.image(thumb, caption=f"Image {idx + 1}", use_column_width=True)

            # 수동 태깅
            selected_tag = st.selectbox(f"이미지 {idx + 1} 분류", tag_options, key=f"tag_{idx}")
            tag_data[file.name] = selected_tag

# --- Step 4 & 5: 제목 추천 ---
if user_idea and uploaded_files:
    st.divider()
    if st.button("✨ 매력적인 제목 10개 생성"):
        with st.spinner("AI가 제목을 고민 중입니다..."):
            prompt = f"[{category}] 주제: {user_idea}. 업로드된 사진 종류: {list(tag_data.values())}. 네이버 블로그 검색 최적화 제목 10개를 번호 매겨서 추천해줘."
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            st.session_state.titles = response.choices[0].message.content.split("\n")

    if st.session_state.titles:
        st.session_state.selected_title = st.selectbox("마음에 드는 제목을 선택하세요", st.session_state.titles)

# --- Step 6: 본문 생성 ---
# --- Step 6: 본문 생성 및 해시태그 추천 ---
if st.session_state.selected_title:
    if st.button("📝 블로그 본문 및 태그 생성"):
        with st.spinner("본문과 해시태그 20개를 생성 중입니다..."):
            img_info = "\n".join([f"- {name}: {tag}" for name, tag in tag_data.items()])

            full_prompt = f"""
            제목: {st.session_state.selected_title}
            주제: {user_idea}
            카테고리: {category}

            이미지 정보:
            {img_info}

            위 정보를 바탕으로 다음 조건에 맞춰 글을 작성해줘:
            1. 분량: 1,500자이상 상세한 본문.
            2. 고정 인사말 : 방하! 오늘은 ~~~ 
            3. 이미지 배치: 본문 중간중간 [IMAGE_파일명_태그]를 삽입할 것.
            4. 말투: 친근한 블로그 어투 (~해요, ~했답니다).
            5. 이모지 사용: 문장 사이에 적절한 이모지를 풍부하게 넣어줘.
            6. 고정 클로징 : 함바! ~~~

            [해시태그 추가 요청]
            - 본문 맨 마지막에 해당 주제와 관련된 해시태그 20개를 생성해줘.
            - 형식은 #태그명 형태이며, 띄어쓰기 없이 나열해줘.
            - 맛집/여행지 이름, 지역구, 메뉴명, 분위기(데이트, 주말나들이 등), 블로그 소통 태그를 골고루 섞어줘.
            """

            final_res = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": full_prompt}]
            )

            blog_result = final_res.choices[0].message.content

            st.markdown("---")
            st.subheader("✅ 완성된 포스팅 및 추천 태그")

            # 텍스트 영역에 출력 (복사하기 편하도록)
            st.text_area("내용을 복사해서 블로그에 사용하세요", blog_result, height=700)

            # 별도의 해시태그 미리보기 영역 (선택사항)
            if "#" in blog_result:
                tags_only = blog_result.split("#")
                st.info(f"💡 추천 태그 {len(tags_only) - 1}개가 생성되었습니다.")

            st.download_button(
                label="결과를 텍스트 파일로 저장",
                data=blog_result,
                file_name="blog_post_with_tags.txt",
                mime="text/plain"
            )