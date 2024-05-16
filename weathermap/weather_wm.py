import requests
import json
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from kakao import send

today = datetime.today().strftime("%Y%m%d")

def weather(nx,ny):
    api_key = "85hmTOqqno6bPzurtS3Kehoh5FPFtpaUhLkk14l8I/3tOnROTqRRPjCwbY5HgdLF04FlaURUQaeqXvoB0EK5Tw=="
    base_date = today
    base_time = "0500"

    url = f'http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst?serviceKey={api_key}&pageNo=1&numOfRows=1000&dataType=JSON&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}'
    response = requests.get(url, verify=False)

    return response


response = weather(61,126) #서울
#response = weather(60,121) #수원

if response.status_code == 200:
    res = json.loads(response.text)
    try:
        # category : TMP : 온도, SKY : 하늘 상태, PCP : 강수량, PTY: 강수형태, REH:습도
        sky_code = {'1': '맑음', '3': '구름많음', '4': '흐림'}
        pty_code = {'0': '화창', '1': '비', '2': '비눈', '3': '눈', '5': '빗방울', '6': '진눈깨비', '7': '눈날림'}
        informations = dict()

        for data in res['response']['body']['items']['item']:
            if data['fcstDate'] == today:
                if data['fcstTime'] == '0600' or data['fcstTime'] == '1400':
                    cate = data['category']
                    fcstTime = data['fcstTime']
                    fcstValue = data['fcstValue']
                    temp = dict()
                    temp[cate] = fcstValue

                    if fcstTime not in informations.keys():
                        informations[fcstTime] = dict()
                    informations[fcstTime][cate] = fcstValue

    except Exception as e:
        print('LOG: Error [%s]' % (str(e)))
        exit()
    else:
        msg = f"오늘의 날씨 (오전/오후)" \
              f"\n기온 : {informations['0600']['TMP']}°C / {informations['1400']['TMP']}°C" \
              f"\n습도 : {informations['0600']['POP']}% / {informations['1400']['POP']}%" \
              f"\n구름 : {sky_code[informations['0600']['SKY']]} / {sky_code[informations['1400']['SKY']]}"\
              f"\n강수 : {informations['0600']['PCP']} / {informations['1400']['PCP']}"\
              f"\n풍속 : {informations['0600']['WSD']}m/s / {informations['1400']['WSD']}m/s"
        send.kakao(msg)
else:
    print('통신 오류')