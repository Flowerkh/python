import base64
import time
import os
import sys
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *
from PyQt5 import uic
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
os.system('chcp 65001')

form_class = uic.loadUiType("poketmon.ui")[0]
target_url = "https://brand.naver.com/samlip/products/6510954368";

class WindowClass(QMainWindow, form_class) :
    def __init__(self) :
        super().__init__()
        self.setupUi(self)
        self.GUI_main()

        self.pushButton.clicked.connect(self.buttonclick)

    def buttonclick(self):
        self.main()

    # 메인 UI
    def GUI_main(self):
        self.setWindowTitle('poketmon 사고만다')
        self.setWindowIcon(QIcon('./img/kh_icon.png'))
        self.move(950, 300)
        self.setFixedSize(330, 440)
        self.plainTextEdit.setReadOnly(True)
        self.lineEdit_2.setEchoMode(QLineEdit.Password)

    def main(self):
        QApplication.processEvents()
        self.plainTextEdit.appendPlainText('INFORMATION: 페이지 새고고침 시간 [%s]로 설정되었습니다.' % (1))
        self.plainTextEdit.appendPlainText(f'INFORMATION: 매크로 작동 횟수 [{self.re_cnt.value()}] 회로 설정되었습니다.')
        try:
            driver = self.get_driver()
            driver.get('https://nid.naver.com/nidlogin.login?mode=form&url=https%3A%2F%2Fwww.naver.com')
            id = base64.b64decode(base64.b64encode(self.lineEdit.text().encode('ascii'))).decode("UTF-8")
            pw = base64.b64decode(base64.b64encode(self.lineEdit_2.text().encode('ascii'))).decode("UTF-8")
            QApplication.processEvents()
            self.login_naver(driver, id, pw)  # 네이버 로그인
            time.sleep(1)
            QApplication.processEvents()
            driver.get(target_url)  # 타겟팅할 페이지 이동
            QApplication.processEvents()
            self.plainTextEdit.appendPlainText('LOG: 타켓팅 페이지[%s] 이동 성공' % ('https://brand.naver.com/samlip/products/6510954368'))

            macro_count = 1
            # 실행
            while (self.check_order(driver, macro_count)):
                QApplication.processEvents()
                macro_count += 1
                time.sleep(int(1))
                if (macro_count > int(self.re_cnt.value()) and int(self.re_cnt.value()) != -1):
                    QApplication.processEvents()
                    self.plainTextEdit.appendPlainText("LOG: 매크로 작동 가능 횟수를 넘어 프로그램이 종료됩니다.")
                    break

        except Exception as e:
            self.plainTextEdit.appendPlainText('LOG: Error [%s]' % (str(e)))
        else:
            self.plainTextEdit.appendPlainText("LOG: Main Process in done.")
        finally:
            os.system("Pause")
            driver.quit()

    def check_order(self, driver, macro_count):  # 재고 확인 및 구매
        QApplication.processEvents()
        driver.refresh()
        elements = driver.find_elements_by_css_selector('#content > div > div._2-I30XS1lA > div._2QCa6wHHPy > fieldset > div.XqRGHcrncz > div:nth-child(1) > div > a._2-uvQuRWK5')
        if (len(elements) > 0):
            QApplication.processEvents()
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "._2-uvQuRWK5"))).click()  # 구매 버튼 클릭
            self.plainTextEdit.appendPlainText("INFORMATION: 현재 상품 재고가 있습니다 구매를 시도합니다.")

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH,'//*[@id="chargePointScrollArea"]/div[1]/ul[1]/li[4]/div[1]/span[1]/span'))).click()  # 일반결제 선택
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH,'//*[@id="chargePointScrollArea"]/div[1]/ul[1]/li[4]/ul/li[3]/span[1]/span'))).click()  # 나중에 결제 버튼 클릭
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="orderForm"]/div/div[7]/button'))).click()  # 결재 버튼 클릭
            self.plainTextEdit.appendPlainText("INFORMATION: 주문 요청을 전송하였습니다 마이페이지에서 결과확인 및 결제를 진행하여 주십시오.")
            self.plainTextEdit.appendPlainText("INFORMATION: 프로그램을 종료합니다")
        else:
            QApplication.processEvents()
            self.plainTextEdit.appendPlainText('INFORMATION: [%d][%s]%s' % (macro_count, driver.title, '현재 상품이 품절 상태입니다.'))
            return True

    # 크롬 버전 관리
    def get_driver(self):
        c_path = self.browser_path.text()
        chrome_options = webdriver.ChromeOptions()
        driver = webdriver.Chrome(c_path, options=chrome_options)
        return driver

    def login_naver(self, driver, id, pw):
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
        self.plainTextEdit.appendPlainText("LOG: 네이버 로그인 성공")
        return False

if __name__ == "__main__" :
    app = QApplication(sys.argv)
    myWindow = WindowClass()
    myWindow.show()

    sys.exit(app.exec_())