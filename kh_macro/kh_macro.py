import os
import sys
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *
from PyQt5 import uic

#UI파일 연결
#단, UI파일은 Python 코드 파일과 같은 디렉토리에 위치해야한다.
form_class = uic.loadUiType("kh_macro.ui")[0]

#화면을 띄우는데 사용되는 Class 선언
class WindowClass(QMainWindow, form_class) :
    def __init__(self) :
        super().__init__()
        self.setupUi(self)
        self.GUI_main()

        #button event
        self.pushButton.clicked.connect(lambda :self.buttonclick('jandi'))

    #btn Eventhandler
    def buttonclick(self, val):
        if val == 'jandi':
            os.system('"C:\\Users\\GECL\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Tosslab Inc\\JANDI.lnk"')
        elif val == 'sqlyog':
            os.system('"C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\SQLyog - 64 bit\\SQLyog.lnk"')
        else:
            QMessageBox.about(self, 'note', '미구현 기능입니다.')

    # 메인 UI
    def GUI_main(self):
        self.setWindowTitle('경하의 매크로')
        self.setWindowIcon(QIcon('./img/kh_icon.png'))
        self.move(300, 300)
        self.setFixedSize(300, 300)  # (width,heigh)

if __name__ == "__main__" :
    app = QApplication(sys.argv)
    myWindow = WindowClass()
    myWindow.show()

    app.exec_()