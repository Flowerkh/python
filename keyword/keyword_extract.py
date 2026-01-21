# -*- coding: utf-8 -*-
"""
용도 : Flask 개발 시 필요한 모듈
"""
from flask import request
from flask import abort, make_response, jsonify
from http import HTTPStatus
import json

from datetime import datetime, timezone, timedelta, date
from functools import wraps
import lib.env as env
from lib.db import queryone, execute
import os

KST = timezone(timedelta(hours=9))


def authenticate(f):
    """
    Compares with the token and determine to authenticate.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        Authorization = request.headers.get('Authorization')

        if Authorization is None:
            error_msg = "Authentication failed."
            log_http_request_response(error_msg, HTTPStatus.UNAUTHORIZED)
            abort(HTTPStatus.UNAUTHORIZED, error_msg)

        list_request_token = Authorization.split()
        if list_request_token[0] != 'Bearer' or list_request_token[1] != env.AUTH_TOKEN:
            abort(HTTPStatus.UNAUTHORIZED, 'Authentication failed.')
        else:
            return f(*args, **kwargs)

    return decorated_function


def is_production_server():
    """
        현재 서버가 production 서버인지 development 서버인지 확인
    """
    if is_local_server():
        return False
    return env.PROJECT_ID == 'gentok'


def is_local_server():
    """
        현재 서버가 local 인지 gcloud 인지 확인
    """
    return not os.getenv('GAE_ENV', '').startswith('standard')


def now():
    """
    현재 시간을 MySQL timestamp에 넣을 수 있는 형식으로 변환하여 리턴함.
    """
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')


def now_pgsgw_form():
    """
    현재 시간을 MySQL timestamp에 넣을 수 있는 형식으로 변환하여 리턴함.
    """
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M')


def now_task_id_form():
    """
    현재 시간을 Task 생성 시 TASK_ID로 약속한 형식으로 변환하여 리턴함.
    # * `TASK_ID` can contain only letters ([A-Za-z]), numbers ([0-9]),
    #   hyphens (-), or underscores (_). The maximum length is 500 characters.
    """
    return datetime.now(KST).strftime('%Y%m%d-%H%M%S-%f')


def now_date_form():
    """
    현재 시간을 yyyy-mm-dd 형식으로 리턴함.
    """
    return datetime.now(KST).strftime('%Y-%m-%d')


def request_logging(f):
    """
    request_logging
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        log = dict()
        log["headers"] = str(request.headers).replace("\r\n", " | ")
        log["mimetype"] = request.mimetype
        if request.mimetype == "application/json":
            log["data"] = request.json
        if request.mimetype == "application/x-www-form-urlencoded":
            log["data"] = request.form.to_dict(flat=False)
        else:
            log["data"] = request.data
        print(">>> req (", f.__name__, ") :", log)
        return f(*args, **kwargs)

    return decorated_function


def log_http_request_response(response_data={},
                              response_status=HTTPStatus.NO_CONTENT,
                              request_date=None,
                              response_date=None,
                              memo=None):
    # 현재 시간 가져오기
    api_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 요청 정보 가져오기
    client_ip = request.headers.get('X-Real-IP', request.remote_addr)
    request_method = request.method
    request_uri = request.url
    request_header = json.dumps(dict(request.headers))
    request_type = request.headers.get('Content-Type')
    request_data = json.dumps(request.json)

    # SQL 쿼리를 사용하여 데이터 삽입
    insert_query = """
    INSERT INTO api_log_table_msa (
        api_date,
        api_type,
        client_ip,
        request_method,
        request_uri,

        request_header,
        request_type,
        request_data,
        request_date,
        response_status,

        response_data,
        response_date,
        memo
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    q_result = execute('b2b', insert_query, (api_date,
                                             'PDF',
                                             client_ip,
                                             request_method,
                                             request_uri,
                                             request_header,
                                             request_type,
                                             request_data,
                                             request_date,
                                             response_status.value,
                                             json.dumps(response_data, ensure_ascii=False),
                                             datetime.now(),
                                             memo))

    if q_result.error is not None:
        return str(q_result.error), HTTPStatus.INTERNAL_SERVER_ERROR

    return True


# Utility functions for date and time serialization
def serialize_for_json(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


def compare_between_dates(date1, date2):
    """
        두 날짜 사이의 날짜 차이를 반환
        예) compare_between_dates('2020-01-01', '2020-01-02')
            return 1
        ref: https://stackoverflow.com/questions/1828948/mysql-function-to-find-the-number-of-working-days-between-two-dates/6762805#6762805
    """
    if date1 == date2:
        return 0
    elif date1 < date2:
        start_date = date1
        end_date = date2
    else:
        start_date = date2
        end_date = date1

    q_result = queryone(('b2b',
                         '''
                            SELECT 5 * (DATEDIFF(%s, %s) DIV 7) 
                                   + MID('0123444401233334012222340111123400012345001234550', 7 * WEEKDAY(%s) + WEEKDAY(%s) + 1, 1) 
                                   - (SELECT COUNT(*) 
                                        FROM z_holiday_data 
                                       WHERE 1=1
                                         AND DAYOFWEEK(holiday_date) BETWEEN 1 AND 6
                                         AND holiday_date >= %s 
                                         AND holiday_date < %s) AS result
                        '''), (end_date, start_date, start_date, end_date, start_date, end_date))

    if q_result.error is not None:
        return abort(make_response(jsonify(q_result.error), 500))

    return int(q_result.rows['result'])


def compare_between_unix_timestamp(timestamp1, timestamp2):
    """
        두 unix timestamp 사이의 시간 차이를 반환
        예) compare_between_unix_timestamp(1578288800, 1578291200)
            return 120
    """
    return timestamp1 - timestamp2


def get_holiday_count_include_start_date(start_date, end_date):
    get_holiday_result = queryone('b2b', '''
        SELECT count(*) AS holidays
        FROM tb_lims_holiday
        WHERE cldr_ymd >= %s
            AND cldr_ymd <= %s
    ''', (start_date, end_date))

    if get_holiday_result.error is None:
        return get_holiday_result.rows['holidays']


def get_holiday_count_exclude_start_date(start_date, end_date):
    get_holiday_result = queryone('b2b', '''
        SELECT count(*) AS holidays
        FROM tb_lims_holiday
        WHERE cldr_ymd > %s
            AND cldr_ymd <= %s
    ''', (start_date, end_date))

    if get_holiday_result.error is None:
        return get_holiday_result.rows['holidays']


def add_holiday_calc(start_date, end_date):
    start_date_str = start_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')

    holiday_cnt = get_holiday_count_exclude_start_date(start_date_str, end_date_str)

    added_end_date = end_date + timedelta(days=holiday_cnt)

    # 다음날부터 1일 카운트
    tommerow_datetime = start_date + timedelta(days=1)

    for _date in range(((added_end_date + timedelta(days=1)) - tommerow_datetime).days):
        if (tommerow_datetime + timedelta(days=_date)).weekday() > 4:
            return add_holiday_calc(tommerow_datetime + timedelta(days=_date), added_end_date + timedelta(days=1))

    return end_date


def get_check_pdf_cache(response_info):
    check_pdf_cache = queryone('b2b', '''
           SELECT request_info
           FROM check_pdf_cache
           WHERE response_info = %s
       ''', (response_info,))

    if check_pdf_cache.error is None:
        if check_pdf_cache.rows is None:
            return ''
        else:
            return check_pdf_cache.rows['request_info']


def insert_check_pdf_cache(response_info, request_info, created_date):
    insert_query = '''
        INSERT INTO check_pdf_cache(response_info, request_info, created_date)
        VALUES(%s, %s, %s)
    '''
    insert_query_result = execute('b2b', insert_query,
                                  (response_info, request_info, created_date.strftime('%Y-%m-%d %H:%M:%S')))

    if insert_query_result.error is None:
        return True
