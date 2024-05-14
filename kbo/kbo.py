import sys,os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from pyvirtualdisplay import Display

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from kakao import send
try:
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    #service = Service(executable_path=r'C:/project/python/python/chromedriver.exe')
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    service = Service(excutable_path=r'/var/project/python/chromedriver.exe')
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(3)

except Exception as e:
    print('LOG: Error [%s]' % (str(e)))
    exit()
else:
    print("LOG: Main Process in done.")

driver.get('https://www.koreabaseball.com/')
full_html = driver.page_source
driver.quit()
soup = BeautifulSoup(full_html, 'html.parser')
temp = soup.find_all(class_="game-cont")

game_list = []
place_list = {'잠실':'[잠실]\n', '문학':'[문학]\n', '수원':'[수원]\n', '대전':'[대전]\n', '광주':'[광주]\n'}

for v in temp:
    game_text = v.text.replace(' TICKETPREVIEW','').replace(' VS',f"{v.attrs['away_nm']} : {v.attrs['home_nm']}")
    game_list.append(game_text.replace('선','').replace('경기예정',' '))
for key in place_list.keys():
    game_list = [game_list[i].replace(key, place_list[key]) for i in range(len(game_list))]
game = '\n'.join(game_list)
msg = f"오늘의 경기\n{game}"

print(msg)
#send.kakao(msg)