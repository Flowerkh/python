#split() = 공백 기준으로 텍스트를 구분함 ex) a b -> a, b
a, b = input("곱셈할 두 수를 입력하세요").split();
print(f"두 수의 곱은 {int(a) * int(b)}입니다.")