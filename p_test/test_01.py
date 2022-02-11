#class

class arr:
    a = ["Seoul", "Kyeonggi", "Inchon", "Daejoen", "Deagu", "Pusan"]
    str01=' '
    
    def showMsg(self): #생성자
        print(self.str01)

    for i in a:
        str01 = str01 + i[0]

print_on = arr()
print_on.showMsg()