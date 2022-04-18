from datetime import date, datetime
import os

today = date.today()
now = datetime.now()

print(os.path.dirname(os.path.abspath(__file__)))
