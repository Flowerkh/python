import random
import time

print("welcom To")
print("Math Quiz!!")

playing = True
score = 0
count = 0

start_time = time.time() #경과 시간
while playing :
    num1 = random.randint(1,9)
    num2 = random.randint(1,9)
    num3 = random.randint(1,9)

    answer = num1 * num2 - num3
    user_input = int(input(f"{num1}x{num2}-{num3} = "))
    count += 1

    if answer == user_input:
        score += 1
        print(f"정답입니다. 현재 점수는 {score}점 입니다.")
    else :
        playing = False
        print(f"틀렸습니다. 정답은 {answer} 입니다.")

end_time = time.time()
print(f"총 {count}문제를 {round(end_time-start_time)}초만에 해결하였습니다.")
print("Quiz가 종료되었습니다.")