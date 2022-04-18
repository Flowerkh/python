import requests
from bs4 import BeautifulSoup
import re

char_name = '웅크린양'
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
        print(char_jem)
        print(jem_lev_list)
        for lev in jem_lev_list:
            if (lev.find('감소') > 0):
                user_jem_lev.append(f"홍염 {jem_lev[lev]} : {char_jem[cnt]}")
            else:
                user_jem_lev.append(f"멸화 {jem_lev[lev]} : {char_jem[cnt]}")
            cnt += 1
    except Exception as e:
        pass

    if(len(char_jem) > 0):
        pass
    else:
        user_jem_lev = '보석이 없습니다.'

    for i in range(0,len(char_card_set1)):
        card_option.append(f"{re.sub('<.+?>', '', str(char_card_set1[i]))} : {re.sub('<.+?>', '', str(char_card_set2[i]))}")

    #각인
    for ability in char_ability:
        pass
        #print(re.sub('<.+?>', '', str(ability)))
    char_skill = {
        "버서커":"순간 받는 피해 12% 증가", "데모닉":"순간 받는 피해 12% 증가", "워로드":"순간 받는 피해 3% 증가\n상시 몬스터 방어력 감소 12%\n순간 백&헤드 데미지 9% 증가\n정화(상태이상 해제/넬라시아의 기운)", "인파이터":"상시 받는 피해 6% 증가", "호크아이":"상시 받는 피해 6% 증가", "소서리스":"상시 받는 피해 6% 증가", "블레이드":"상시 받는 피해 3%증가\n상시 백&헤드 데미지 9% 증가",
        "창술사":"순간 치명타 적중률 18%", "배틀마스터":"순간 치명타 적중률 18%", "스트라이커":"순간 치명타 적중률 18%", "데빌헌터":"상시 치명타 적중률 10%", "건슬링어":"상시 치명타 적중률 10%", "아르카나":"상시 치명타 적중률 10%",
        "기공사":"상시 공격력 6%증가\n정화(상태이상 해제/내공 방출)", "스카우터":"상시 공격력 6%증가",
        "디스트로이어":"순간 몬스터 방어력 감소 24%", "서머너":"순간 몬스터 방어력 감소 24%\n정화(상태이상 해제/레이네의 가호)","블래스터":"상시 몬스터 방어력 감소 12%",
        "리퍼":"상시 치명타 피해 20% 증가",
        "홀리나이트":"정화(상태이상 해제/신성한 보호)"
    }
    char_job = soup.select_one('#lostark-wrapper > div > main > div > div.profile-character-info > img').get('alt')

else:
    print(response.status_code)