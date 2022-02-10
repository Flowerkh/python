print("지금부터 타이머 시작을 누르고 문제를 풀어보세요")
second = int(input("총 몇 초가 소요되었나요?"))

minute = second // 60
remainder = second % 60

print(f"총 {minute}분 {remainder}초가 소요되었습니다.")
