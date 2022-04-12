from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import base64
import os
import json
import base64
import argparse
import time

def get_driver():
    driver = webdriver.Chrome("C:/Users/GECL/smartstore-macro-master/chromedriver.exe")
    return driver

def get_config():
	try:
		with open('config.json') as json_file:
			json_data = json.load(json_file)
	except Exception as e:
		print('LOG: Error in reading config file, {}'.format(e))
		return None
	else:
		return json_data

def main():
	try:
		driver = get_driver() #크롬 드라이버 로딩
		driver.get('https://nid.naver.com/nidlogin.login?mode=form&url=https%3A%2F%2Fwww.naver.com')
		config = get_config() #설정 파일 가져오기
		id = base64.b64decode(config['userId']).decode("UTF-8") # id,pw 의 base64 decode
		pw = base64.b64decode(config['userPw']).decode("UTF-8")
		login_naver(driver, id, pw) #네이버 로그인

	except Exception as e:
		print('LOG: Error [%s]' % (str(e.decode("UTF-8"))))
	else:
		print("LOG: Main Process in done.")
	finally:
		os.system("Pause")
		driver.quit()

def login_naver(driver, id, pw):
    script = "                                      \
    (function execute(){                            \
        document.querySelector('#id').value = '" + id + "'; \
        document.querySelector('#pw').value = '" + pw + "'; \
    })();"
    driver.execute_script(script)

    element = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".btn_login"))
    )
    element.click()
    print("LOG: 네이버 로그인 성공")
    return False

main()