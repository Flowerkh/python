# -*-coding:utf-8-*-
# :::::::::::::: 서명 이미지 용량 확인 스크립트               ::::::::::::::
# :::::::::::::: by. jack                                ::::::::::::::
# :::::::::::::: by. way 26.06.15 수정                     ::::::::::::::
import os
import re
import smtplib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os.path import isfile

import pymysql


def get_svg_signature_extent(svg_file_name):
    """모든 좌표의 x, y 범위(가로·세로 길이)를 반환. 빈 파일이면 (0, 0), 파싱 실패면 None."""
    try:
        tree = ET.parse(svg_file_name)
    except ET.ParseError:
        return None  # XML 파싱 실패 → 비정상, 확인 필요

    xs, ys = [], []
    for elem in tree.getroot().iter():
        tag = elem.tag.split('}')[-1]  # 네임스페이스 제거
        coord_str = ''
        if tag == 'path':
            coord_str = elem.get('d', '')
        elif tag in ('polyline', 'polygon'):
            coord_str = elem.get('points', '')
        elif tag == 'circle':
            cx = elem.get('cx')
            cy = elem.get('cy')
            if cx: xs.append(float(cx))
            if cy: ys.append(float(cy))
            continue

        nums = [float(n) for n in re.findall(r'-?\d+\.?\d*', coord_str)]
        xs.extend(nums[0::2])  # 짝수 인덱스 = x
        ys.extend(nums[1::2])  # 홀수 인덱스 = y

    if not xs or not ys:
        return (0.0, 0.0)

    return (max(xs) - min(xs), max(ys) - min(ys))


def get_svg_viewbox(svg_file_name):
    """SVG viewBox 범위 반환. 없으면 None."""
    try:
        tree = ET.parse(svg_file_name)
    except ET.ParseError:
        return None

    root = tree.getroot()
    viewbox = root.get('viewBox', '')
    if not viewbox:
        # viewBox 없으면 width/height attribute로 대체
        w = root.get('width')
        h = root.get('height')
        if w and h:
            return (0, 0, float(w), float(h))
        return None

    parts = viewbox.split()
    if len(parts) == 4:
        return tuple(float(p) for p in parts)  # (min_x, min_y, width, height)
    return None


def is_svg_out_of_bounds(svg_file_name):
    """서명 좌표가 viewBox 밖으로 벗어났는지 확인. 벗어나면 True, 정상이면 False, 판단불가면 None."""
    try:
        tree = ET.parse(svg_file_name)
    except ET.ParseError:
        return None  # 파싱 실패

    viewbox = get_svg_viewbox(svg_file_name)
    if not viewbox:
        return None  # viewBox 없으면 판단 불가

    vx, vy, vw, vh = viewbox

    xs, ys = [], []
    for elem in tree.getroot().iter():
        tag = elem.tag.split('}')[-1]
        coord_str = ''
        if tag == 'path':
            coord_str = elem.get('d', '')
        elif tag in ('polyline', 'polygon'):
            coord_str = elem.get('points', '')
        elif tag == 'circle':
            cx = elem.get('cx')
            cy = elem.get('cy')
            if cx: xs.append(float(cx))
            if cy: ys.append(float(cy))
            continue

        nums = [float(n) for n in re.findall(r'-?\d+\.?\d*', coord_str)]
        xs.extend(nums[0::2])
        ys.extend(nums[1::2])

    if not xs or not ys:
        return False  # 좌표 없으면 판단 불가

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    return (min_x < vx or max_x > vx + vw or
            min_y < vy or max_y > vy + vh)


db = pymysql.connect(
    user='macrogen',
    password='dtccore240731#$%',
    host='mbp-prd-dtc-core-agreement.css3utrm7nlw.ap-northeast-2.rds.amazonaws.com',
    port=3307,
    db='b2bapi',
    charset='utf8'
)

cursor = db.cursor()
today = datetime.today().strftime("%Y-%m-%d")
yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

log_file = "/data/script/check_sign_image_size/log/" + today + ".txt"

f = open(log_file, 'w')

select_after5year_question_query = """
    SELECT omics_type
        ,coworker
        ,user_cert_req_number
        ,kitid
    FROM vw_agreement_user
    WHERE user_collect_date = %s
    """
f.write('query : ' + select_after5year_question_query + '\nparam : ' + yesterday + '\n')
cursor.execute(select_after5year_question_query, yesterday)
result = cursor.fetchall()
log = ''

for row in result:
    omics_type = row[0]
    coworker = row[1]
    cert_req_number = row[2]
    kit_id = row[3]
    png_file_name = '/data/agreement_pdf_sign_img/' + omics_type + '/' + coworker + '/sign_' + cert_req_number + '.png'
    svg_file_name = '/data/agreement_pdf_sign_img/' + omics_type + '/' + coworker + '/sign_' + cert_req_number + '.svg'

    # 뱅크샐러드의 빈 png 파일 용량이 950Bytes 정도기 때문에 900Bytes 로 기준을 잡고 확인
    if isfile(png_file_name) and os.path.getsize(png_file_name) < 900:
        log += 'kit id : ' + kit_id + '\n' + png_file_name + ' size : ' + str(
            os.path.getsize(png_file_name)) + 'Bytes\n'
        log += '------------------------------------------------------------------------------------------------\n'

    # SVG 체크: 파일 존재 여부 + 파싱 정상 여부 + 패드 범위 벗어남 여부
    # (점만 찍힌 서명은 통과)
    if isfile(svg_file_name):
        extent = get_svg_signature_extent(svg_file_name)

        # 1. 파싱 실패
        if extent is None:
            log += 'kit id : ' + kit_id + '\n' + svg_file_name + ' SVG 파싱 실패(비정상 파일)\n'
            log += '------------------------------------------------------------------------------------------------\n'

        else:
            # 2. 서명 좌표가 패드 범위 벗어남
            out_of_bounds = is_svg_out_of_bounds(svg_file_name)
            if out_of_bounds:
                log += 'kit id : ' + kit_id + '\n' + svg_file_name + ' 서명이 패드 범위 벗어남\n'
                log += '------------------------------------------------------------------------------------------------\n'

    # SVG 파일 자체가 없는 경우
    else:
        log += 'kit id : ' + kit_id + '\n' + svg_file_name + ' SVG 파일 없음\n'
        log += '------------------------------------------------------------------------------------------------\n'

if log == '':
    pass
else:
    # 1. 세션 생성 및 연결
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()  # TLS 보안 연결

    # 2. 로그인 (중요: 일반 비번이 아닌 '앱 비밀번호' 사용)
    gmail_user = 'mbp.prd@macrogen.com'
    gmail_pw = 'tsoaaffjhjnkdwqv'  # 구글에서 발급받은 16자리 앱 비밀번호
    s.login(gmail_user, gmail_pw)

    msg = MIMEMultipart()
    msg['Subject'] = '서명 이미지 확인 필요 리스트'
    msg.attach(MIMEText(log, 'plain'))

    from_to = gmail_user
    send_to = ['kimjihan@macrogen.com', 'sj99146@macrogen.com', 'hoban@macrogen.com']

    # 5. 메일 전송 및 종료
    s.sendmail(from_to, send_to, msg.as_string())
    s.quit()

f.write(log)
f.close()
cursor.close()
db.close()