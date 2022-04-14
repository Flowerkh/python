import datetime
import os

now = datetime.datetime.now()
path = "./discord/log/"
if not os.path.isdir(path):
    os.mkdir(path)

f = open(path+f"chat_log_{str(now.year)}{str(now.month)}{str(now.day)}.log", 'a')
f.write("\naa")

f.close()