# 한국투자 자동매매 프로그램

### 사전 작업
1. https://securities.koreainvestment.com/main/Main.jsp > 서비스 신청 > Open API > KIS Developers > KIS Developers 서비스 신청하기 
2. KIS_key.json 파일 생성
```json
{
  "id": "발급받은 ID",
  "account" : "사용할 계좌",
  "sub_account" : "계좌 뒷 2자리",
  "app_key": "발급받은 APP KEY",
  "app_secret": "발급받은 APP_SECRET KEY"
}
```
3. token.txt 파일 생성
---
* 변수 값
  * Request 
    * KIND 
      * 해외 주식
        > HKS : 홍콩, NYS : 뉴욕, NAS : 나스닥, AMS : 아멕스, TSE : 도쿄, SHS : 상해, SZS : 심천, SHI : 상해지수, SZI : 심천지수, HSX : 호치민, HNX : 하노이
      * 국내 
        > J : 주식, ETF, ETN
  * Response
    * tr_id
      * 해외
        > JTTT1002U : 미국 매수 주문, JTTT1006U : 미국 매도 주문, TTTS0308U : 일본 매수 주문, TTTS0307U : 일본 매도 주문, TTTS0202U : 상해 매수 주문, TTTS1005U : 상해 매도 주문, TTTS1002U : 홍콩 매수 주문, TTTS1001U : 홍콩 매도 주문
      * 국내
        > TTTC0802U : 주식 현금 매수 주문, TTTC0801U : 주식 현금 매도 주문
    * OVRS_EXCG_CD
      * 해외
        > NASD : 나스닥, NYSE : 뉴욕, AMEX : 아멕스, SEHK : 홍콩, SHAA : 중국상해, SZAA : 중국심천, TKSE : 일본
---
* def info @request_param
> ovrs_pdno : 해외상품번호\
ovrs_item_name : 해외종목명\
frcr_evlu_pfls_amt : 외화평가손익금액\
evlu_pfls_rt : 평가손익율\
pchs_avg_pric : 매입평균가격\
ovrs_cblc_qty : 해외잔고수량\
ord_psbl_qty : 주문가능수량(매도 가능한 주문 수량)\
frcr_pchs_amt1 : 외화매입금액1(해당 종목의 외화 기준 매입금액)\
ovrs_stck_evlu_amt : 해외주식평가금액(해당 종목의 외화 기준 평가금액)\
now_pric2 : 현재가격2(해당 종목의 현재가)\
tr_crcy_cd : USD : 미국달러 , HKD : 홍콩달러 , CNY : 중국위안화 , JPY : 일본엔화 , VND : 베트남동\
ovrs_excg_cd : NASD : 나스닥 , NYSE : 뉴욕 , AMEX : 아멕스 , SEHK : 홍콩 , SHAA : 중국상해 , SZAA : 중국심천 , TKSE : 일본 , HASE : 하노이거래소 , VNSE : 호치민거래소\
LOAN_TYPE_CD : 대출유형코드\
loan_dt : 대출일자\
expd_dt : 만기일자
