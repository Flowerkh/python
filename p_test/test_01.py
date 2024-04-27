def switch(operator,num1,num2):
    return {
        '+': num1 + num2,
        '-': num1 - num2,
        '*': num1 * num2,
        '/': num1 / num2,
    }.get(operator, "안댐 돌아가")

def calculator():
    num1 = float(input("숫자: "))
    operator = input("골라 (+, -, *, /): ")
    num2 = float(input("숫자: "))

    print(f'{switch(operator,num1,num2)}')

while True:
    calculator()
    repeat = input("또해 시발?: ")
    if repeat == "N":
        break

#메인 함수 실행
if __name__ == "__main__":
	calculator()