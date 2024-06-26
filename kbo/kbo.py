from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

try:

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.implicitly_wait(3)

    driver.get('https://www.koreabaseball.com/')
    full_html = driver.page_source
    driver.quit()
    soup = BeautifulSoup(full_html, 'html.parser')
    temp = soup.find_all(class_="game-cont")

    game_list = []
    place_list = {'잠실':'[잠실]\n', '문학':'[문학]\n', '수원':'[수원]\n', '대구':'[대구]\n', '창원':'[창원]\n', '대전':'[대전]\n', '광주':'[광주]\n', '고척':'[고척]\n'}

    for v in temp:
        game_text = v.text.replace(' TICKETPREVIEW','').replace(' VS',f"{v.attrs['away_nm']} : {v.attrs['home_nm']}")
        game_list.append(game_text.replace('선','').replace('경기예정',' '))
    for key in place_list.keys():
        game_list = [game_list[i].replace(key, place_list[key]) for i in range(len(game_list))]
    game = '\n'.join(game_list)
    msg = f"오늘의 경기\n{game}\n등말소 현황 : https://www.koreabaseball.com/Player/RegisterAll.aspx"

except Exception as e:
    print('LOG: Error [%s]' % (str(e)))
    exit()
else:
    print("LOG: Main Process in done.")

    print(msg)