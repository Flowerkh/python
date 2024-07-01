import sys
import requests
from bs4 import BeautifulSoup

date = sys.argv[1]
site_name = sys.argv[2]
type_name = sys.argv[3]
file_name = sys.argv[4]

res = requests.get("http://statistics.gentok.net/chatgenestatic/popup/"+file_name+".php?site="+site_name+"&type="+type_name+"&date="+date)
html_code = BeautifulSoup(res.text, "html.parser")
html_code.encode('utf-8')
with open("C:/project/ga_api/test/buyStatic_popup_"+date+".html", "w") as html_code:
    html_code.write(html_code)

html_file = open("/var/www/html/my-genomestory/chatgene/popup/"+file_name+"_"+site_name+"_"+type_name+"_"+date+".html", "w",encoding="utf-8")
html_file.write(str(html_code))
html_file.close()
