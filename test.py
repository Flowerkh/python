import time
import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from pyvirtualdisplay import Display
from bs5 import BeautifulSoup

def mk_crawl_to_php(chrome_driver, php_name):
    url_pre = 'https://statistics.gentok.net/chatgenestatic/'
    loc_pre = '/var/www/html/my-genomestory/chatgene/'
    chrome_driver.get(url_pre+php_name)

    #print(url_pre+php_name + ' url insert')
    time.sleep(10)
    html = chrome_driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    html_context = """
                <?php
                    session_start();
                    if(!$_SESSION['user_email']){
                ?>
                <script>alert('로그인 해주세요');</script>
                <?php
                        echo("<meta http-equiv='refresh' content='0;url=login.php'>");
                    }
                    else{
                ?>
            """

    html_context = html_context + soup.prettify()
    html_context = html_context + """
                <?php
                    }
                ?>
            """
#    if php_name != 'index' and php_name != 'in_member' :
#        html_context = html_context + "상세페이지 미러링 개발 작업중입니다."

    with open(loc_pre+php_name, 'w') as f:
        f.write(html_context)

    f.close()


display = Display(visible=0, size=(1920, 1080))
display.start()

service = Service(executable_path=r'/home/chrome_driver/chromedriver')
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=chrome_options)

url = 'https://statistics.gentok.net/chatgenestatic/login.php'

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#print(now)

id = 'jeongsun@macrogen.com'
passwd = 'mg0605'

#print('into the url')
driver.get(url)

driver.execute_script("document.getElementById('user_email').value='"+id+"'")
#print('input id')
driver.execute_script("document.getElementById('user_password').value='"+passwd+"'")
#print('input passwd')
time.sleep(5)
driver.find_element(By.XPATH, '/html/body/div/div/div/div/div/div/form/input').click()
#print('next button')
time.sleep(10)
#print('login success')

mk_crawl_to_php(driver, 'index.php')
mk_crawl_to_php(driver, 'in_member.php')

driver.close()
driver.quit()
display.stop()

#print('done')
