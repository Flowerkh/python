import sys
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *
from PyQt5 import uic
from thread_list import *

form_class = uic.loadUiType("kh_macro.ui")[0]

class WindowClass(QMainWindow, form_class) :
    def __init__(self) :
        super().__init__()
        self.setupUi(self)
        self.GUI_main()

        self.jandi.clicked.connect(lambda :self.buttonclick('jandi'))
        self.sql.clicked.connect(lambda :self.buttonclick('sqlyog'))

    def buttonclick(self, val):
        QApplication.processEvents()
        if val == 'jandi':
            x = jandi_thread(self)
            x.start()

        elif val == 'sqlyog':
            x = sql_thread(self)
            x.start()
        else:
            QMessageBox.about(self, 'note', '미구현 기능입니다.')

    def GUI_main(self):
        self.setWindowTitle('경하의 매크로')
        self.setWindowIcon(QIcon('./img/kh_icon.png'))
        self.move(300, 300)
        self.setFixedSize(300, 300)

if __name__ == "__main__" :
    app = QApplication(sys.argv)
    myWindow = WindowClass()
    myWindow.show()

    app.exec_()