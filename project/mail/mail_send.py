import smtplib
from datetime import date, timedelta
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import os

today = date.today()
yesterday = date.today() - timedelta(1)

token_path = os.path.dirname(os.path.abspath(__file__))+"/login.txt"
t = open(token_path, "r", encoding="utf-8")
lines = t.readlines()
for line in lines:
    token = lines

smtp_imfo = dict({
    'smtp_server': 'smtp.gmail.com',
    'smtp_user_id': token[0],
    'smtp_user_pw': token[1],
    'smtp_port': 587,
})
smtp = smtplib.SMTP(smtp_imfo['smtp_server'], smtp_imfo['smtp_port'])
smtp.ehlo()
smtp.starttls()
smtp.login(token[0].strip(),token[1])

recipients = ["cdffee1@naver.com"]
message = MIMEMultipart()
message['Subject'] = f'{yesterday.strftime("%Y-%m-%d")} 카카오 refresh_key 재발급'
message['From'] = 'qbxlrudgk1@gmail.com'
message['To'] = ",".join(recipients)
content = f'첨부파일 확인하여 refresh_key 재발급이 필요합니다.'
minetext = MIMEText(content, 'html')
message.attach(minetext)

#첨부 파일
attachments = [os.path.join(os.getcwd(), './kakao.zip')]
for attachment in attachments:
    attach_binary = MIMEBase("application", "octet-stream")
    try:
        binary = open(attachment, 'rb').read()

        attach_binary.set_payload(binary)
        encoders.encode_base64(attach_binary)

        filename = os.path.basename(attachment)
        attach_binary.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(filename))

        message.attach(attach_binary)
    except Exception as e:
        print(e)
smtp.sendmail(message['From'], recipients, message.as_string())

smtp.quit()