#값이 다르고, 참조도 다른 경우
a = 1
b = 2

print(f"a 값, 주소 : '{a}, {hex(id(a))}")
print(f"b 값, 주소 : '{b}, {hex(id(b))}")

print(f"a == b : {a == b}")
print(f"a is b : {a is b}")

##값과 참조가 같을 때
c = ['block','dmask']
d = c
print(f"c 값, 주소 : '{c}, {hex(id(c))}")
print(f"d 값, 주소 : '{d}, {hex(id(d))}")

if c == d:
    print("== True")
else :
    print("== false")

if c is d :
    print("is True")
else :
    print("is false")

## 값은 같고 참조가 다름
e = [1,2,3]
f = [1,2,3]

print(f"e 값, 주소 : '{e}, {hex(id(e))}")
print(f"f 값, 주소 : '{f}, {hex(id(f))}")

print(f"e == f : {e==f}")
print(f"e is f : {e is f}")