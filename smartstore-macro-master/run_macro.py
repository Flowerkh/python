# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
import os
import json
import base64
import argparse
import time

# 인자값을 받을 수 있는 인스턴스 생성
parser = argparse.ArgumentParser(description='네이버 스토어 자동구매 매크로 도움말 입니다.')
# 입력받을 인자값 등록
parser.add_argument('--target', required=False, help='타겟팅 사이트 설정')
parser.add_argument('--time', required=False, default = 2, help='페이지 새고고침 시간 설정 [기본값 2초]')
parser.add_argument('--count', required=False, default = 2, help='매크로 작동 횟수 설정 [기본값 9999회]')
parser.add_argument('--option1', required=False, help='구매시 옵션1 선택이 필요한 경우 선택할 옵션을 숫자로 입력 [두번째 옵션을 선택하고자 하면 2]')
parser.add_argument('--option2', required=False, help='구매시 옵션2 선택이 필요한 경우 선택할 옵션을 숫자로 입력 [두번째 옵션을 선택하고자 하면 2]')
parser.add_argument('--option3', required=False, help='구매시 옵션3 선택이 필요한 경우 선택할 옵션을 숫자로 입력 [두번째 옵션을 선택하고자 하면 2]')
args = parser.parse_args()

c_path = "C:/Users/GECL/smartstore-macro-master/chromedriver.exe";
target_url = "https://brand.naver.com/samlip/products/6510954368";
if(args.target):
    target_url = args.target

def main():
	try:
		driver = get_driver()
		driver.get('https://nid.naver.com/nidlogin.login?mode=form&url=https%3A%2F%2Fwww.naver.com')
		config = get_config()
		id = base64.b64decode(config['userId'])
		id = id.decode("UTF-8")
		pw = base64.b64decode(config['userPw'])
		pw = pw.decode("UTF-8")
		login_naver(driver, id, pw) #네이버 로그인
		time.sleep(1)
		driver.get(target_url) #타겟팅할 페이지 이동
		print('LOG: 타켓팅 페이지[%s] 이동 성공' % ('https://brand.naver.com/samlip/products/6510954368'))
		macro_count = 1

        #실행
		while(check_order(driver, macro_count)):
			macro_count += 1
			time.sleep(int(args.time))
			if (macro_count > int(args.count) and int(args.count) != -1):
				print("LOG: 매크로 작동 가능 횟수를 넘어 프로그램이 종료됩니다.")
				break
	except Exception as e:
		print('LOG: Error [%s]' % (str(e)))
	else:
		print("LOG: Main Process in done.")
	finally:
		os.system("Pause")
		driver.quit()

def get_config():
	try:
		with open('config.json') as json_file:
			json_data = json.load(json_file)
	except Exception as e:
		print('LOG: Error in reading config file, {}'.format(e))
		return None
	else:
		return json_data

#크롬 버전 관리
def get_driver():
    options = Options()
    options.add_argument("start-maximized")
    driver = webdriver.Chrome(c_path, options=options)
    return driver

def login_naver(driver, id, pw):
    script = "                                      \
    (function execute(){                            \
        document.querySelector('#id').value = '" + id + "'; \
        document.querySelector('#pw').value = '" + pw + "'; \
    })();"
    driver.execute_script(script)

    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".btn_login"))
    )
    element.click()
    print("LOG: 네이버 로그인 성공")
    return False

def check_order(driver, macro_count): #재고 확인 및 구매
    driver.refresh()
    elements = driver.find_elements_by_css_selector('#content > div > div._2-I30XS1lA > div._2QCa6wHHPy > fieldset > div.XqRGHcrncz > div:nth-child(1) > div > a._2-uvQuRWK5')
    if(len(elements) > 0):
        if args.option1 != None:
            driver.find_element_by_xpath("//*[@id=\"wrap\"]/div/div[2]/div[2]/form/fieldset/div[4]/div[1]/ul/li[1]/ul/li[1]/div/select/option[%d]" % (int(args.option1) + 1)).click()
        if args.option2 != None:
            driver.find_element_by_xpath("//*[@id=\"wrap\"]/div/div[2]/div[2]/form/fieldset/div[4]/div[1]/ul/li[1]/ul/li[2]/div/select/option[%d]" % (int(args.option2) + 1)).click()
        if args.option3 != None:
            driver.find_element_by_xpath("//*[@id=\"wrap\"]/div/div[2]/div[2]/form/fieldset/div[4]/div[1]/ul/li[1]/ul/li[3]/div/select/option[%d]" % (int(args.option3) + 1)).click()
        
        #옵션 여부
        options = driver.find_elements_by_css_selector('#content > div > div._2-I30XS1lA > div._2QCa6wHHPy > fieldset > div.bd_2dy3Y')
        if(len(options) > 0):
            print("INFORMATION: 해당 상품에 옵션이 있습니다.")
            #옵션 선택
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="content"]/div/div[2]/div[2]/fieldset/div[6]'))).click()
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="content"]/div/div[2]/div[2]/fieldset/div[6]/div/ul/li[1]/a'))).click()

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "._2-uvQuRWK5"))).click() #구매 버튼 클릭
        print("INFORMATION: 현재 상품 재고가 있습니다 구매를 시도합니다.")

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="chargePointScrollArea"]/div[1]/ul[1]/li[4]/div[1]/span[1]/span'))).click() #일반결제 선택
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="chargePointScrollArea"]/div[1]/ul[1]/li[4]/ul/li[3]/span[1]/span'))).click() #나중에 결제 버튼 클릭
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="orderForm"]/div/div[7]/button'))).click() #결재 버튼 클릭
        print("INFORMATION: 주문 요청을 전송하였습니다 마이페이지에서 결과확인 및 결제를 진행하여 주십시오.")
        print("INFORMATION: 프로그램을 종료합니다")
    else:
        print('INFORMATION: [%d][%s]%s' % (macro_count, driver.title, '현재 상품이 품절 상태입니다.'))
        return True

if __name__ == '__main__':
    print('INFORMATION: 페이지 새고고침 시간 [%s]로 설정되었습니다.' % (args.time))
    print('INFORMATION: 매크로 작동 횟수 [%s]로 설정되었습니다.' % (args.count))
    if args.option1 != None:
        print('INFORMATION: 옵션1의[%s] 번을 선택합니다' % (args.option1))
    if args.option2 != None:
        print('INFORMATION: 옵션2의[%s] 번을 선택합니다' % (args.option2))
    if args.option3 != None:
        print('INFORMATION: 옵션3의[%s] 번을 선택합니다' % (args.option3))
    main()