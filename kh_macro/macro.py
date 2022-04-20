import sys
import pyautogui
import os
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *

class khMacro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.jandi()
        self.Sql()
        self.inputTest()
        self.GUI_main()

    # 잔디
    def jandi(self):
        btn = QPushButton('jandi 실행', self)
        btn.move(5, 5)
        btn.clicked.connect(lambda:self.buttonclick('jandi'))
        self.default()

    # sql
    def Sql(self):
        btn = QPushButton('sqlyog 실행', self)
        btn.move(110,5)
        btn.clicked.connect(lambda:self.buttonclick('sqlyog'))
        self.default()

    def inputTest(self):
        self.line = QLineEdit(self)
        self.line.move(5,35)

        self.line2 = QLineEdit(self)
        self.line2.move(5, 100)

        btn = QPushButton('input Test', self)
        btn.move(160, 35)
        btn.clicked.connect(lambda:self.inputbuttonEvent('test'))
        self.default()

    def inputbuttonEvent(self, flag):
        #self.line.clear() #삭제
        print(self.line.text())
        print(self.line.text())

    #button setting
    def buttonclick(self, val):
        if val == 'jandi':
            os.system('"C:\\Users\\GECL\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Tosslab Inc\\JANDI.lnk"')
        elif val == 'sqlyog':
            os.system('"C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\SQLyog - 64 bit\\SQLyog.lnk"')
        else:
            QMessageBox.about(self, 'note', '미구현 기능입니다.')

    # 기타
    def etc(self):
        etc = QPushButton('기타', self)
        etc.move(215, 5)

    def default(self):
        pyautogui.moveTo(894, 536)

    #메인 UI
    def GUI_main(self):
        self.setWindowTitle('경하의 매크로')
        self.setWindowIcon(QIcon('./img/kh_icon.png'))
        self.setFixedSize(700, 500)  # (width,heigh)
        self.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = khMacro()
    app.exec_()

# while True:
#     currentWidth, currentHeight = pyautogui.position()  # 현재 마우스 위치
#     if keyboard.is_pressed('esc'):
#         print('프로그램을 종료합니다.')
#         break
#     elif keyboard.is_pressed('j'): #잔디
#
#     else:
#         pass