# -*-coding:utf-8-*-
import os
import sys
import datetime
from datetime import timedelta
import glob
import subprocess
import pymysql

today = datetime.date.today()
yesterday = today - timedelta(days=1)
#yesterday = datetime.date(2026, 5, 20)
# DB 접속 (실제 운영 환경에서는 환경변수나 설정파일 조회를 권장합니다)
try:
    db = pymysql.connect(
        user='macrogen',
        password='dtccore240731#$%',
        host='mbp-prd-dtc-core-agreement.css3utrm7nlw.ap-northeast-2.rds.amazonaws.com',
        port=3307,
        db='b2bapi',
        charset='utf8'
    )
    cursor = db.cursor(pymysql.cursors.DictCursor)
except Exception as e:
    print(f"DB 연결 실패: {e}")
    sys.exit(1)

# 1. 대상 키트아이디 목록 조회 (파라미터 바인딩 적용)
bio_sql = """
    SELECT LEFT(user_agree_time,10) AS date, GROUP_CONCAT(kitid) AS kitid_list 
    FROM tb_agreement_user 
    WHERE LEFT(user_agree_time,10) = %s 
    GROUP BY LEFT(user_agree_time,10)
"""

cursor.execute(bio_sql, (str(yesterday),))
bio_result = cursor.fetchall()

# 데이터가 없는 경우 안전하게 종료
if not bio_result:
    print(f"[{today}] {yesterday} 날짜에 해당하는 동의 내역 데이터가 없습니다. 종료합니다.")
    db.close()
    sys.exit(0)

bio_date = bio_result[0]['date']
kitid_arr = bio_result[0]['kitid_list']
kitid_list = kitid_arr.split(',') if kitid_arr else []

agreement_num = 0
tb_name = 'vw_agreement_user'  # 뱅크샐러드 분기가 필요하다면 테이블명 동적 처리 검토 필요

# 2. 키트별 PDF 재생성 및 관리 루프
for kitid in kitid_list:
    kitid = kitid.strip()
    if not kitid:
        continue

    # SQL 인젝션 방지를 위해 테이블 이름 외의 조건은 파라미터 바인딩 처리
    # (단, 테이블 이름은 바인딩이 안 되므로 안전한 문자열인지 사전 검증 필요)
    select_agree_query = f"""
        SELECT vgu.*, tcc.content AS pdf_format
        FROM {tb_name} AS vgu
        LEFT JOIN tb_coworker_content AS tcc 
            ON vgu.coworker = tcc.coworker AND tcc.id = 'pdf_url' AND service = 'genome'
        WHERE vgu.kitid = %s
            AND del = 0
            AND agreement_num IN (0,1)
    """

    try:
        cursor.execute(select_agree_query, (kitid,))
        result = cursor.fetchall()

        if not result:
            continue

        coworker = result[0]['coworker']
        relation = result[0]['relation']
        is_question9 = result[0]['question9']
        is_question10 = result[0]['question10']
        user_cert_req_number = result[0]['user_cert_req_number'] if result[0]['user_cert_req_number'] else ' '

        if agreement_num != 0:
            kitid = f"{kitid}-{agreement_num}"

        # 파일명 정의
        if coworker == 'banksalad':
            origin_pdf_name = f"{kitid}_agreement.pdf"
        else:
            origin_pdf_name = f"{kitid}_{user_cert_req_number}_agreement.pdf"

        ori_pdf_dir = f"/data/Services/agreement_pdf/genome/{coworker}/"
        biobank_pdf_dir = f"/biobank/for_customer_dl_human_material_donate_genome/{coworker}/"
        biobank_pdf_name = f"{kitid}_{user_cert_req_number}_dl_human_material_donate.pdf"
        full_biobank_path = os.path.join(biobank_pdf_dir, biobank_pdf_name)

        # 뱅크샐러드가 아닐 때만 파일 처리
        if coworker != 'banksalad':
            if is_question10 == 'true':
                # 디렉토리 생성
                os.makedirs(biobank_pdf_dir, exist_ok=True)

                # pdftk 페이지 분기
                pages = '7-8' if is_question9 == 'true' else '5-6'

                # pdftk 실행 전 원본 파일이 진짜 존재하는지 파이썬으로 먼저 체크
                origin_pdf_path = os.path.join(ori_pdf_dir, origin_pdf_name)
                if not os.path.exists(origin_pdf_path):
                    print(f"⚠️ 원본 파일이 서버에 존재하지 않아 스킵합니다. (경로: {origin_pdf_path})")
                    continue  # 다음 키트로 넘어감

                # os.system 대신 subprocess.run 사용
                cmd = ['pdftk', origin_pdf_path, 'cat', pages, 'output', full_biobank_path]
                print(f"실행 명령어: {' '.join(cmd)}")
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

                if res.returncode == 0:
                    print(f"성공: biobank_pdf_command!! {kitid}")
                else:
                    # 파이썬 버전별 호환성을 위해 res.stderr가 문자열인지 확인 후 출력
                    error_msg = res.stderr if isinstance(res.stderr, str) else res.stderr.decode('utf-8',
                                                                                                 errors='ignore')
                    print(f"실행 에러 ({kitid}): {error_msg}")

            else:
                # 동의 철회 유저 파일 안전하게 삭제 (find -delete 대신 파ืน 내장 기능 이용)
                # 안전장치: 잘못된 경로 삭제 방지를 위해 glob 패턴 구체화
                search_pattern = os.path.join(biobank_pdf_dir, f"{kitid}*.pdf")
                files_to_delete = glob.glob(search_pattern)

                for file_path in files_to_delete:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"삭제 완료: {file_path}")

                print(f"finish biobank_pdf_command_delete!! {kitid}")

    except Exception as e:
        # 특정 키트 처리 중 에러가 발생해도 스크립트가 죽지 않고 다음 키트로 넘어가도록 처리
        print(f"❌ 키트 {kitid} 처리 중 예상치 못한 에러 발생: {e}", file=sys.stderr)
        continue

db.close()
print("모든 작업이 완료되었습니다.")