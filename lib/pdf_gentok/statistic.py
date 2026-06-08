import time
import random
from datetime import datetime, timedelta
import os
import threading
import subprocess
import sys

import csv
from pathlib import Path
import jwt
import requests
import gzip

from common import decompress_gzip
from config import APPLE_VENDER_NUM, APPLE_API_KEY, APPLE_ISSUER_ID, ROOT_PATH

import mysql.connector

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from pyvirtualdisplay import Display

#-----------------------------------------------------------------------------------------------------------------
# const
script_name = "ga_daily_mobile_count.py"
script_path = "/home/py_test/ga_api_git/ga_api/ga_modules/ga_daily_mobile_count.py"
log_path = "/home/py_test/ga_api_git/ga_api/ga_modules/ga_daily_mobile_count_log.txt"
error_log_path = "/home/py_test/ga_api_git/ga_api/ga_modules/ga_daily_mobile_count_error.txt"

google_crop_url = 'https://play.google.com/console/u/0/developers/7007031280734551498/app/4972902767864080011/statistics?metrics=USER_ACQUISITION-NEW-EVENTS-PER_INTERVAL-DAY'

date_format = "%Y-%m-%d"
datetime_format = "%Y-%m-%d %H:%M:%S"

google_id = 'gentokmgs@gmail.com'
google_pwd = 'Thffntusroqkfqn!'

date_file = "/home/py_test/ga_api_git/ga_api/ga_modules/date_not_updated.txt"
android_prefix="android:"
ios_prefix="ios:"
reupdated_prefix="reupdated:"
split_char=","

key_android='android'
key_ios='ios'
key_reupdated='reupdated'

#-----------------------------------------------------------------------------------------------------------------
# functions - rerun
def check_already_running():
    result = subprocess.getoutput("ps -ef | grep 'python'")
    return result.count(script_name) > 2

def rerun():
    with open(log_path, "a") as f:
        subprocess.Popen(["python3" ,script_path], stdout=f)

def start_rerun_timer():
    timer_thread = threading.Timer(60 * 30, rerun)
    timer_thread.start()


#-----------------------------------------------------------------------------------------------------------------
# functions - google
def get_google_count_list(target_date, update_list, reupdated):
    result = { }

    display = Display(visible=0, size=(1920, 1080))
    display.start()

    service = Service(executable_path=r'/home/py_test/chromedrivers/chromedriver')
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')  # 샌드박스 비활성화
    chrome_options.add_argument("--disable-dev-shm-usage")  # 메모리 문제 방지
    chrome_options.add_argument("--disable-gpu")  # GPU 관련 문제 해결
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # 자동화 탐지 방지
    chrome_options.add_argument("--lang=ko-KR")  # 한국어 지원
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print(f"Into the Google URL : {google_crop_url}")
        driver.get(google_crop_url)

        # 매크로 의심 블록을 피하기 위해 sleep 시간 랜덤 지정
        random_cnt = random.randrange(5, 15)
        random_cnt2 = random.randrange(5, 15)
        random_cnt3 = random.randrange(5, 15)
        random_cnt4 = random.randrange(10, 20)

        time.sleep(5)
        driver.execute_script("document.getElementById('identifierId').value='"+google_id+"'")
        print('Input google ID')
        time.sleep(random_cnt)
        driver.find_element(By.XPATH, '//*[@id="identifierNext"]/div/button').click()
        print('Next button')
        time.sleep(random_cnt2)
        driver.execute_script("document.getElementsByName('Passwd')[0].value='"+google_pwd+"'")
        print('Input google passwd')
        time.sleep(random_cnt3)
        driver.find_element(By.XPATH, '//*[@id="passwordNext"]/div/button').click()
        print('Next button')
        time.sleep(random_cnt4)

        print('Google Login success')

        # android count는 웹사이트에서 받으므로 내부에서 값 업데이트를 수행한다.
        tag_prefix = '//*[@id="main-content"]/div/div[1]/div/page-router-outlet/page-wrapper/div/statistics-page/app-statistics/stats-table/console-block-1-column/div/div/console-table/div/div/ess-table/ess-particle-table/div[1]/div/div[2]/div['
        date_suffix = ']/ess-cell[1]/console-table-text-cell/div/div[1]/span'
        download_suffix = ']/div/div/ess-cell[1]/console-table-text-cell/div/div[1]/span'

        last_updated = reupdated

        for i in range(11, 1, -1):
            date_tag = tag_prefix + str(i) + date_suffix
            download_tag = tag_prefix + str(i) + download_suffix

            date = driver.find_element(By.XPATH, date_tag).text
            date_check = datetime.strptime(date, '%Y년 %m월 %d일').strftime(date_format)
            print(f"Row {i}: date={date_check}, target={target_date}")
            download_cnt = driver.find_element(By.XPATH, download_tag).text.replace(',','')

            if date_check == target_date:
                print('AOS parsing date : ' + target_date)

                if download_cnt.strip() != '':
                    print('AOS download count : ' + download_cnt)
                    result[target_date] = download_cnt
                else:
                    print('AOS download count is not updated yet')
                    result[target_date] = -1
            elif update_list is not None and date_check in update_list:
                result[date_check] = download_cnt

            if i > 6 and datetime.strptime(last_updated, date_format) < datetime.strptime(date_check, date_format):
                last_updated = date_check
                result[date_check] = download_cnt

        result[key_reupdated] = last_updated

        if update_list is not None:
            for day in update_list:
                if day not in result:
                    add_element(result ,key_android, day)
    except Exception as e:
        print(f"Error : {e}")
        start_rerun_timer()
    finally:
        driver.quit()
        os.system('pkill -f Xvfb')

    return result


#-----------------------------------------------------------------------------------------------------------------
# functions - apple
def get_apple_count_list(target_date, update_list):
    result = { }

    result[target_date] = get_apple_count(target_date)

    if update_list is not None:
        for date_str in update_list:
            result[date_str] = get_apple_count(date_str)

    return result

def get_apple_count(date):
    current_epoch = int(time.time())
    token_time = 30 #30 sec
    expiration_time = current_epoch + token_time

    api_sub_url = f"/v1/salesReports?filter[frequency]=DAILY&filter[reportDate]={date}&filter[reportSubType]=SUMMARY&filter[reportType]=SALES&filter[vendorNumber]={APPLE_VENDER_NUM}"

    jwt_header = {
        "alg": "ES256",
        "kid": APPLE_API_KEY,
        "typ": "JWT"
    }

    jwt_payload = {
        "iss": APPLE_ISSUER_ID,
        "iat": current_epoch,
        "exp": expiration_time,
        "aud": "appstoreconnect-v1",
        "scope" : [
            f"GET {api_sub_url}"
        ]
    }

    with open(f"{ROOT_PATH}/AuthKey_{APPLE_API_KEY}.p8", "rb") as fh:
        private_key = fh.read()
        encoded_jwt = jwt.encode(payload=jwt_payload, headers=jwt_header, algorithm="ES256", key=private_key)

    api_url = f"https://api.appstoreconnect.apple.com{api_sub_url}"
    print(f"APPLE URL : {api_url}")

    session = requests.Session()

    headers = {
        'Authorization': f'Bearer {encoded_jwt}'
    }

    response = session.get(api_url, headers=headers)
    iphone_cnt = 0
    ipad_cnt = 0

    try:
        if response.status_code == 200:
            print('APPLE API STATUS 200')
            file_path = f'{ROOT_PATH}/apple_data.csv'

            data = decompress(response)
            data = data.replace('\t', ',')

            file = Path(file_path)
            file.write_text(data, 'utf-8')

            f = open(file_path, "r", encoding='UTF-8')
            reader = csv.reader(f)

            for idx, row in enumerate(reader):
                if row[4] == '젠톡(GenTok)' and row[6] == '1':
                    if row[22] == 'iPad':
                        ipad_cnt = ipad_cnt + int(row[7])
                    elif row[22] == 'iPhone':
                        iphone_cnt = iphone_cnt + int(row[7])

            print('ipad download count : ' + str(ipad_cnt))
            print('iphone download count : ' + str(iphone_cnt))

            return ipad_cnt, iphone_cnt
        else:
            print(response.text)
            return -1, -1
    except Exception as e:
        print(f"Error : {e}")
        start_rerun_timer()

#-----------------------------------------------------------------------------------------------------------------
# functions - server
def insert_count(google_cnt, ipad_cnt, iphone_cnt, date):
    print('Connect db')

    connection = mysql.connector.connect(
        host='mbp-prd-mariadb-statistics.css3utrm7nlw.ap-northeast-2.rds.amazonaws.com',
        port='8306',
        database='macrogen',
        user='macrogen',
        password='dnakwps58!'
    )

    if connection.is_connected():
        cursor = connection.cursor()
        print('Insert db')

        full_date = date + " 00:00:00"

        is_update = False
        sql_check = "select 1 from tb_download where reg_date = %(date)s"
        cursor.execute(sql_check, { 'date': full_date })

        if cursor.fetchone() is not None:
            is_update = True
        else:
            is_update = False

        sql_pre = "SELECT aos_acs, ios_acs FROM tb_download ORDER BY reg_date DESC LIMIT 1"

        last_aos_acs = 0
        last_ios_acs = 0

        cursor.execute(sql_pre)
        result = cursor.fetchone()
        if result:
            last_aos_acs, last_ios_acs = result

        if is_update is False:
            sql = """
                INSERT INTO tb_download (AOS, aos_acs, ios_pad, ios_iphone, ios_acs, reg_date)
                VALUES ( %s, %s, %s, %s, %s, %s )
            """
            cursor.execute(sql, (int(google_cnt), int(google_cnt) + last_aos_acs, int(ipad_cnt), int(iphone_cnt), int(ipad_cnt) + int(iphone_cnt) + last_ios_acs, full_date))
        else:
            sql = """
                UPDATE tb_download SET AOS = %s, aos_acs = %s, ios_pad = %s, ios_iphone = %s, ios_acs = %s WHERE reg_date = %s
            """
            cursor.execute(sql, (int(google_cnt), int(google_cnt) + last_aos_acs, int(ipad_cnt), int(iphone_cnt), int(ipad_cnt) + int(iphone_cnt) + last_ios_acs, full_date))

        connection.commit()

        if cursor:
            cursor.close()
        if connection:
            connection.close()

        print('Success')
    else:
        print('DB connect Error')

def update_count(google_cnt, ipad_cnt, iphone_cnt, date):
    print('Connect db')
    connection = mysql.connector.connect(
        host='mbp-prd-mariadb-statistics.css3utrm7nlw.ap-northeast-2.rds.amazonaws.com',
        port='8306',
        database='macrogen',
        user='macrogen',
        password='dnakwps58!'
    )

    if connection.is_connected():
        cursor = connection.cursor()
        print('Update db')

        full_date = date + " 00:00:00"
        sql = "UPDATE tb_download SET "
        params = []

        if int(google_cnt) >= 0:
            sql += "AOS = %s"
            params.append(int(google_cnt))

        if int(google_cnt) >= 0 and int(iphone_cnt) >= 0:
            sql += ", "

        if int(iphone_cnt) >= 0:
            sql += "ios_pad = %s, ios_iphone = %s"
            params.append(int(ipad_cnt))
            params.append(int(iphone_cnt))

        sql += " WHERE reg_date = %s"
        params.append(full_date)

        cursor.execute(sql, tuple(params))

        connection.commit()

        if cursor:
            cursor.close()
        if connection:
            connection.close()

        print('Success')
    else:
        print('DB connect Error')


#-----------------------------------------------------------------------------------------------------------------
# functions - file
def read_data_update_needed():
    result = { }

    if os.path.exists(date_file):
        try:
            with open(date_file, 'r') as file:
                for line in file:
                    if line.startswith(android_prefix):
                        result[key_android] = line.replace(android_prefix, '').replace('\n', '').split(split_char)
                    elif line.startswith(ios_prefix):
                        result[key_ios] = line.replace(ios_prefix, '').replace('\n', '').split(split_char)
                    elif line.startswith(reupdated_prefix):
                        result[key_reupdated] = line.replace(reupdated_prefix, '').replace('\n', '').split(split_char)
        except FileNotFoundError:
            pass

    return result

def write_data_update_needed(data):
    with open(date_file, 'w') as file:
        if key_android in data:
            file.write(android_prefix + split_char.join(str(item) for item in data[key_android]) + '\n')
        if key_ios in data:
            file.write(ios_prefix + split_char.join(str(item) for item in data[key_ios]) + '\n')
        if key_reupdated in data:
            file.write(reupdated_prefix + split_char.join(str(item) for item in data[key_reupdated]) + '\n')


#-----------------------------------------------------------------------------------------------------------------
# functions - other
def add_element(data, key, value):
    if value != '' and key in data:
        if isinstance(data[key], list):
            data[key].extend(value)
        elif isinstance(data[key], set):
            data[key].add(value)
        else:
            data[key] += value
    else:
        data[key] = { value }

def decompress(response):
    content = response.content

    if content[:2] == b'\x1f\x8b':
        try:
            content = gzip.decompress(content)
        except Exception as e:
            print(f"Error on decompress : {e}")
            return None

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as e:
        print(f"Error decoding UTF-8: {e}")
        return None

#-----------------------------------------------------------------------------------------------------------------
# functions - main
def main():
    now = datetime.now().strftime(datetime_format)
    remain = { }

    target_date = (datetime.today() - timedelta(days=3)).strftime(date_format)
    update_list = read_data_update_needed()

    print(f"\nSTART : {now}")
    print("Retreiving new data")

    google_cnt = 0
    ipad_cnt = 0
    iphone_cnt = 0

    last_updated = update_list.get(key_reupdated)[0] if key_reupdated in update_list else '2000-01-01'

    google = get_google_count_list(target_date, update_list.get(key_android), last_updated)
    if target_date not in google or google[target_date] == -1:
        print('target date not found')
        add_element(remain, key_android, target_date)
    else:
        google_cnt = google[target_date]

    if key_reupdated in google:
        print('key_reupdated date found')
        add_element(remain, key_reupdated, google[key_reupdated])

    if key_android in google:
        for item in google[key_android]:
            add_element(remain, key_android, item)

    apple = get_apple_count_list(target_date, update_list.get(key_ios))
    if target_date not in apple or apple[target_date][1] == -1:
        add_element(remain, key_ios, target_date)
    else:
        ipad_cnt = apple[target_date][0]
        iphone_cnt = apple[target_date][1]

    if key_ios in apple:
        for item in key_ios:
            add_element(remain, key_ios, item)

    print("Write to db")

    #insert
    insert_count(google_cnt, ipad_cnt, iphone_cnt, target_date)

    #update
    for date, cnt in google.items():
        if date != target_date and isinstance(cnt, int):
            update_count(cnt, -1, -1, date)

    for date, cnt in apple.items():
        if date != target_date and isinstance(cnt, int):
            update_count(-1, cnt[0], cnt[1], date)

    write_data_update_needed(remain)

    print('complete')

# run main function
if __name__ == "__main__":
    main()
