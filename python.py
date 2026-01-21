import json
import os

# JSON 파일들이 들어있는 폴더 경로 (Windows에서 경로 구분자 수정)
folder_path = r'C:\Users\김경하\Desktop\프로젝트\API\gentok\gentok175-data'

# 폴더 내 모든 .json 파일을 찾아 처리
for filename in os.listdir(folder_path):
    if filename.endswith('.json'):  # .json 파일만 처리
        file_path = os.path.join(folder_path, filename)

        # 파일명 추출 후 .json 확장자 제거
        msid = os.path.splitext(os.path.basename(file_path))[0]

        # JSON 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as file:
            json_data = json.load(file)

        # JSON 데이터를 문자열로 변환
        json_data_str = json.dumps(json_data, ensure_ascii=False)  # 한글이 포함되어 있어도 깨지지 않도록 ensure_ascii=False 설정

        # INSERT 쿼리문 생성
        insert_query = f"INSERT INTO tb_msid_data (msid, json_data) VALUES ('{msid}', '{json_data_str}');"

        # 쿼리 출력 (또는 파일로 저장 가능)
        print(insert_query)
