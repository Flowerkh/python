import json
import os

from pymemcache.client.base import Client
from pytz import timezone
from datetime import datetime, timedelta


def lambda_handler(event, context):

    ktc_time = datetime.now(timezone('Asia/Seoul'))
    # 이벤트 시작 시간
    start_time = ktc_time.replace(hour=10, minute=0, second=0, microsecond=0)
    # 이벤트 종료 시간
    end_time = ktc_time.replace(hour=15, minute=1, second=0, microsecond=0)
    ktc_today = ktc_time.strftime("%Y%m%d")

    # memcache 주소
    memcache_addr = 'receptionprocess.kmioik.0001.apn2.cache.amazonaws.com:11211'

    # 당일 memcache 초기화
    if event['queryStringParameters']['selectLang'] == 'clear':
        # memcache Connection
        memcache_client = Client(memcache_addr)
        # 당일 Count 0 으로 초기화
        memcache_client.set(ktc_today, 0)

        return {
            'statusCode': 200,
            'body': json.dumps({'msg': 'clear'})
        }
    # memcache 전체 초기화
    elif event['queryStringParameters']['selectLang'] == 'flushall':
        # memcache Connection
        memcache_client = Client(memcache_addr)
        # memcache 전체 초기화
        memcache_client.flush_all()

        return {
            'statusCode': 200,
            'body': json.dumps({'msg': 'flush all memcache'})
        }
    # 시간내 접근 시
    elif start_time < ktc_time and ktc_time < end_time:
        # parameter로 받은 user 식별용 UUID
        user_real_id = event['queryStringParameters']['realID']
        body_dict = {
            'gToken': event['queryStringParameters']['gToken'],
            'isSuc': 'Y'
        }

        # memcache Connection
        memcache_client = Client(memcache_addr)

        # 금일 선착순 인원수 get
        num = memcache_client.get(ktc_today)
        # 중복 지원을 막기위해 UUID memcache 확인
        user_exist = memcache_client.get(user_real_id)

        # 중복 신청이 아닌경우
        if user_exist is None:
            # 해당 유저 신청 카운트
            memcache_client.set(user_real_id, 1)

            # 당일 신청 인원수 체크
            if num is None:
                # 당일 신청 인원 카운트
                num = 1
                memcache_client.set(ktc_today, num)
            else:
                # 선착순 인원 초과시 (선착순 인원)
                if int(num) >= 10:
                    #body_dict['num'] = num
                    body_dict['isSuc'] = 'N'
                    body_dict['error'] = 'over daily limit'
                else:
                    # 당일 신청 인원 카운트
                    num = int(num) + 1
                    memcache_client.set(ktc_today, num)
                    body_dict['num'] = int(num)
        else:
            # 중복 신청일 경우
            #body_dict['count'] = num
            body_dict['isSuc'] = 'N'
            body_dict['error'] = 'already submit'

        return {
            'statusCode': 200,
            'body': json.dumps(body_dict)
        }
    # 시간 외 접근
    else:
        return {
            'statusCode': 200,
            'body': json.dumps({
                'isSuc': 'N',
                'error': 'not submit time'
            })
        }
