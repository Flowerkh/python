import requests
from bs4 import BeautifulSoup
import re

char_name = '알나'
url = 'https://lostark.game.onstove.com/Profile/Character/'+char_name
response = requests.get(url)

if response.status_code == 200:
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    char_stat = []
    char_jem = []
    jem_lev_list = []
    user_jem_lev = []
    card_option = []
    jem_lev = {
        '2.00% 감소': 1, '4.00% 감소': 2, '6.00% 감소': 3, '8.00% 감소': 4, '10.00% 감소': 5, '12.00% 감소': 6, '14.00% 감소': 7, '16.00% 감소': 8, '18.00% 감소': 9, '20.00% 감소': 10,
        '3.00% 증가': 1, '6.00% 증가': 2, '9.00% 증가': 3, '12.00% 증가': 4, '15.00% 증가': 5, '18.00% 증가': 6, '21.00% 증가': 7, '24.00% 증가': 8, '30.00% 증가': 9, '40.00% 증가': 10
    }
    char_img = soup.select_one('#lostark-wrapper > div > main > div > div.profile-character-info > img').get('src')
    char_honor = soup.select_one('#lostark-wrapper > div > main > div > div.profile-ingame > div.profile-info > div.game-info > div.game-info__title > span:nth-child(2)') #칭호
    char_wj_lv = soup.select_one('#lostark-wrapper > div > main > div > div.profile-ingame > div.profile-info > div.level-info > div.level-info__expedition > span:nth-child(2)') #원정대
    char_ft_lv = soup.select_one('#lostark-wrapper > div > main > div > div.profile-ingame > div.profile-info > div.level-info > div.level-info__item > span:nth-child(2)') #전투
    char_item_lv = soup.select_one('#lostark-wrapper > div > main > div > div.profile-ingame > div.profile-info > div.level-info2 > div.level-info2__expedition > span:nth-child(2)') #아이템
    char_hp = soup.select_one('#profile-ability > div.profile-ability-basic > ul > li:nth-child(2) > span:nth-child(2)') #최생
    char_stat_list = soup.select_one('#profile-ability > div.profile-ability-battle > ul') #status
    lis = char_stat_list.findAll("span")
    char_card_set1 = soup.select('#cardSetList > li > div.card-effect__title')
    char_card_set2 = soup.select('#cardSetList > li > div.card-effect__dsc')
    char_ability = soup.select('#profile-ability > div.profile-ability-engrave > div.swiper-container > div.swiper-wrapper > ul.swiper-slide > li > span')
    char_list = soup.select('#expand-character-list > ul > li > span > button > span')
    char_list_arr = []

    #print(soup.select('#expand-character-list'))

    for data in char_list:
        data = re.sub('<.+?>', '',str(data))
        char_list_arr.append(data)

    print(char_list_arr)
    for li in lis:
        li = re.sub('<.+?>', '',str(li))
        char_stat.append(li)
    try:
        char_jewel = soup.select_one('#profile-jewel > div > div.jewel-effect__list > div > ul')
        jewl_list = char_jewel.findAll("p")
        for jewel in jewl_list:
            char_jem.append(re.sub('<.+?>', '', str(jewel)))
            jem_lev_list.append(re.sub('<.+?>', '', str(jewel))[-9:])
        cnt = 0

        for lev in jem_lev_list:
            if (lev.find('감소') > 0):
                user_jem_lev.append(f"홍염 {jem_lev[lev]} : {char_jem[cnt]}")
            else:
                user_jem_lev.append(f"멸화 {jem_lev[lev]} : {char_jem[cnt]}")
            cnt += 1

    except Exception as e:
        pass

    else:
        user_jem_lev = '보석이 없습니다.'

    for i in range(0,len(char_card_set1)):
        card_option.append(f"{re.sub('<.+?>', '', str(char_card_set1[i]))} : {re.sub('<.+?>', '', str(char_card_set2[i]))}")

else:
    print(response.status_code)