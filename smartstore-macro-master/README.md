# 네이버 스마트 스토어 매크로
> 네이버 스마트 스토어 상품을 자동으로 구매해주는 매크로입니다.

품절상품 링크를 입력하면 자동으로 재고 검사 후 재고가 생기면 자동으로 상품을 구매합니다.

## 사용 방법
OS. Windows 10 기준입니다.

1. `https://github.com/Flowerkh/python/edit/master/smartstore-macro-master/` 다운로드
2. `python-3.8.0.exe 설치`
> ※ 설치 시 하단 Add Python 3.8 to PATH 체크
3. `Win + R 키 입력 후 CMD 입력`
4. `pip install selenium 입력`
5. `Chrome 다운로드`
6. `Chrome 실행 후 오른쪽 상단 ... 클릭>도움말(E)>Chrome 정보(G) 클릭 후 Chrome 버전 확인`
7. `https://chromedriver.chromium.org/downloads 에서 자신의 버전과 맞는 Chrome Driver 다운로드`
> ※ Chrome 버전과 Chrome Driver 버전 상이시 에러 발생
8. `다운로드 한 chromedriver.exe 를 매크로가 있는 디렉터리에 복사`
9. `https://www.base64encode.org 에서 자신의 네이버 아이디, 비밀번호 Base64 인코딩`
10. `config.json 파일에 Base64로 인코딩된 자신의 네이버 아이디, 비밀번호 입력`
> ※ 네이버 2단계 로그인 설정 시 매크로 사용 불가
11. `스크립트 실행`
> run_macro.py [--option1 옵션선택] [--option2 옵션선택] [--option3 옵션선택]

### 주의 사항
1. python-3.8.0.exe 설치 시 설치시 하단 Add Python 3.8 to PATH 체크
2. Chrome 버전과 Chrome Driver 버전 상이시 에러발생
3. 네이버 2단계 로그인 설정시 매크로 사용 불가

## 라이선스
이 매크로는 [MIT 라이선스](https://github.com/OneTop4458/smartstore-macro/blob/master/LICENSE)를 적용받습니다.

