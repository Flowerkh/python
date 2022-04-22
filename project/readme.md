# 한국투자 자동매매 프로그램

### 사전 작업
1. https://securities.koreainvestment.com/main/Main.jsp > 서비스 신청 > Open API > KIS Developers > KIS Developers 서비스 신청하기 
2. KIS_key.json 파일 생성
```json
{
  "id": "발급받은 ID",
  "account" : "사용할 계좌",
  "app_key": "발급받은 APP KEY",
  "app_secret": "발급받은 APP_SECRET KEY"
}
```
---------------------------------------
* 변수 값
  * KIND 
    * 해외 주식
      > HKS : 홍콩, NYS : 뉴욕, NAS : 나스닥, AMS : 아멕스, TSE : 도쿄, SHS : 상해, SZS : 심천, SHI : 상해지수, SZI : 심천지수, HSX : 호치민, HNX : 하노이
    * 국내
      > J : 주식, ETF, ETN

  * CODE
    * 해외
      > JTTT1002U : 미국 매수 주문, JTTT1006U : 미국 매도 주문, TTTS0308U : 일본 매수 주문, TTTS0307U : 일본 매도 주문, TTTS0202U : 상해 매수 주문, TTTS1005U : 상해 매도 주문, TTTS1002U : 홍콩 매수 주문, TTTS1001U : 홍콩 매도 주문
    * 국내
      > TTTC0802U : 주식 현금 매수 주문, TTTC0801U : 주식 현금 매도 주문