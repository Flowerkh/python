unlock = "Welcome"
wrong_password = "LOCKED 잘못된 암호입니다."
password = "A1234!"

user_input = input("!!잠금!! 비밀번호를 입력해주세요")

while user_input != 'A1234!':
    print(wrong_password)
    user_input = input("잘못된 비밀번호 입니다. 다시 입력해주세요.")

print(unlock)
print("잠금이 해제되었습니다.")


