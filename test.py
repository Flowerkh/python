import sys
from PyQt5.QtWidgets import *

class Mainwindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('경하의 매크로')
        self.move(300,300)
        self.resize(700,600)
        self.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = Mainwindow()
    app.exec_()