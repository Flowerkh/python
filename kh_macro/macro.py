import sys
import pyautogui
import keyboard
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *


class Mainwindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('경하의 매크로')
        self.setWindowIcon(QIcon('./img/kh_icon.png'))
        self.setGeometry(300,300,300,300)
        self.move(300, 300)
        self.resize(700, 600)
        self.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = Mainwindow()
    app.exec_()

# while True:
#     currentWidth, currentHeight = pyautogui.position()  # 현재 마우스 위치
#     if keyboard.is_pressed('esc'):
#         print('프로그램을 종료합니다.')
#         break
#     elif keyboard.is_pressed('j'): #잔디
#         pyautogui.click(521, 1070, button='left')
#     else:
#         pass