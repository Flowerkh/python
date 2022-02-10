lock = "LOCKED 암호를 입력해주세요"
unlock = "Welcome"
wrong_password = "LOCKED 잘못된 암호입니다."

password = "A1234!"

user_input = input("!!잠금!! 비밀번호를 입력해주세요")

if user_input == password :
    print("잠금이 해제되었습니다.")
    print(unlock)
else :
    print("암호를 잘못 입력하였습니다.")
    print(wrong_password)