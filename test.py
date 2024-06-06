from datetime import datetime

if datetime.now().strftime('%H:%M') >= "21:30":
    print(datetime.now().strftime('%H:%M'))