import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

c_path = "C:/project/python/python/keyword/chromedriver.exe"

def get_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    )
    service = Service(c_path)
    return webdriver.Chrome(service=service, options=chrome_options)


def get_signal_top10_json():
    driver = get_driver()
    driver.get("https://signal.bz")

    time.sleep(4)

    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".rank-text"))
    )

    ranks = driver.find_elements(By.CSS_SELECTOR, ".rank-num")
    words = driver.find_elements(By.CSS_SELECTOR, ".rank-text")

    count = min(10, len(ranks), len(words))

    result = []
    for i in range(count):
        obj = {
            "rank": int(ranks[i].text.strip()),
            "keyword": words[i].text.strip()
        }
        result.append(obj)

    driver.quit()
    return result

if __name__ == "__main__":
    data = get_signal_top10_json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
