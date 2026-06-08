import os
from PyQt5.QtCore import *

#sqlyog 실행
class sql_thread(QThread):
    def __init__(self, parent):
        super().__init__(parent)
    def run(self):
        os.system('"C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\SQLyog - 64 bit\\SQLyog.lnk"')

#잔디 실행
class jandi_thread(QThread):
    def __init__(self, parent):
        super().__init__(parent)
    def run(self):
        os.system('"C:\\Users\\GECL\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Tosslab Inc\\JANDI.lnk"')