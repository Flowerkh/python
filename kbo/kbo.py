import sys,os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from kakao import send

chrome_options = Options()
chrome_options.add_argument("--headless")
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))

driver.implicitly_wait(3)

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

send.kakao(msg)