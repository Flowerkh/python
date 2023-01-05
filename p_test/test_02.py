import xlwings as xw
from datetime import datetime

today = datetime.today().strftime("%Y%m%d")
name = "invites_export"
file_name = f"{today}_{name}.xls"

path = "C:\\Users\\김경하\\Desktop\\이미지 변환\\"
#path = "\\data\\"

app = xw.App(visible=False)
wb = xw.Book(f"{path}{file_name}")
wb.save(password=today, path=f"{path}{file_name}")
app.kill()