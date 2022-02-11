import random

print("1~20까지 랜덤 숫자가 있습니다. 어떤 숫자일지 맞춰보세요!")

card_num = random.randint(1,20)
user_guess = 0
cnt = 0

while card_num != user_guess:
    cnt += 1
    user_guess = int(input("어떤 숫자일지 맞춰보세요! : "))

    if card_num > user_guess:
        print("up!")
    elif card_num < user_guess:
        print("down")

    print()

print(f"정답 : {card_num}")
print(f"{cnt}번 만에 맞추셨습니다. 정답입니다.")