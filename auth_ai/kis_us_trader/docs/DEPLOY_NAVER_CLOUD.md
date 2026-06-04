# 네이버클라우드 배포 시나리오

> `daily_trader`를 본인 PC가 아닌 클라우드 VM에서 상시 가동하기 위한 가이드.
> 이 워크로드(상시 가동, outbound HTTPS만, 영속 상태 작음)에 클라우드 VM이 자연스러운 선택.
> Phase 0 검증이 PC에서 끝난 후(또는 Phase 1 진입 시점) 이전하는 것을 권장.

---

## 0. 결론

- **가능하다.** 코드 수정 없이 그대로 도는 워크로드.
- 권장 서비스: **Naver Cloud Server (VM)** Micro/Compact 사양.
- 월 비용: **약 ₩15,000~25,000**.
- 결정적 함정: **KIS API IP 화이트리스트 갱신** — 모든 다른 작업보다 우선 수행.

---

## 1. 결정적 함정 — KIS API IP 화이트리스트

한국투자증권 KIS Developers는 **앱키 발급 시 등록한 IP에서만** API 호출이 허용된다(모의/실전 공통).

**현재 상태**: 사용자 PC의 공인 IP가 등록되어 있을 것.
**클라우드 이전 후**: VM의 공인 IP로 KIS 등록을 갱신하지 않으면 **모든 API 호출이 거부**됨.

### 처리 절차
1. 네이버클라우드 VM의 **공인 IP를 고정 IP로 영구 할당** (Naver Cloud "공인 IP" 서비스).
   - ⚠️ 동적 IP면 VM 재시작마다 IP 바뀌어 KIS 재신청 무한반복.
2. KIS Developers 포털 (`apiportal.koreainvestment.com`) 로그인 → 내 앱 → **IP 변경 신청**.
3. 변경 신청한 IP에 클라우드 VM의 고정 IP 입력.
4. 승인까지 영업일 1일 이내.
5. 승인 후 `python test/test_balance_parse.py`로 즉시 검증 (잔고 API는 시간대 무관 동작).

---

## 2. 권장 VM 구성

| 항목 | 권장값 | 이유 |
|---|---|---|
| 서비스 | **Server** (Naver Cloud VM) | 단일 상시 프로세스에 적합. 컨테이너/K8s는 과함 |
| 사양 | **Micro/Compact** (1 vCPU, 1~2 GB RAM) | 메모리 100 MB도 안 쓰는 워크로드. 최저가로 충분 |
| OS | **Ubuntu 22.04 LTS** 또는 Rocky Linux 9 | Python 3.11 설치 쉬움, apt/dnf 친숙 |
| 디스크 | 기본 30 GB SSD | 충분. `.state/` + `logs/` 합쳐도 연 100 MB 미만 |
| 네트워크 | **공인 IP 고정 할당** | KIS IP 등록과 직결. 동적 IP 금지 |
| 보안그룹 | **인바운드 SSH(22)만** (가능하면 본인 IP 제한) | 텔레그램은 outbound long polling, 인바운드 포트 불필요 |
| 시간대 | **KST** (기본값) | `daily_trader.datetime.now()`가 자연스럽게 KST. `state.py`의 ET 변환은 `ZoneInfo`로 명시 처리되므로 host TZ 무관 |

월 비용 추정 (네이버클라우드 2026 기준): Micro VM ₩12k + 고정 IP ₩4k + 스토리지 30GB ₩2k ≈ **₩18,000**.

---

## 3. 셋업 절차 (8단계)

> 이미 KIS Developers에서 VM의 고정 IP를 등록 신청·승인 완료한 상태로 가정.

### 3.1 SSH 접속 + Python 3.11 설치

Ubuntu 22.04 기본 저장소는 Python 3.10까지만 제공합니다. **deadsnakes PPA**로 3.11을 시스템 Python 옆에 추가 설치합니다(시스템 3.10은 그대로 둔다 — apt 등이 의존하므로 절대 손대지 않음).

```bash
ssh user@<VM_PUBLIC_IP>

# OS 확인 (Ubuntu 22.04 가정. Debian/다른 배포판이면 절차가 다름)
cat /etc/os-release

# deadsnakes PPA 추가
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update

# Python 3.11 + venv + 헤더 + git
sudo apt install -y python3.11 python3.11-venv python3.11-dev git

# 설치 검증
python3.11 --version    # → Python 3.11.x 출력되어야 함
python3 --version       # → 여전히 3.10.x (시스템 기본은 안 건드림)
```

> ⚠️ `python3.11`은 시스템에 별도 명령으로 설치됩니다. `python3` 기본값(=3.10)은 그대로. 항상 `python3.11 -m venv .venv`로 가상환경을 만들고, 가상환경 안에서는 `python`이 곧 3.11이 됩니다.

> Debian 12 사용자: deadsnakes는 Ubuntu 전용입니다. 기본 저장소에 `python3.11`이 이미 있으니 `sudo apt install -y python3.11 python3.11-venv python3.11-dev git`만 실행하면 됩니다.

### 3.2 코드 클론 (sparse-checkout으로 kis_us_trader만)

상위 repo가 다른 프로젝트도 포함하는 경우, 전체를 받지 말고 `auth_ai/kis_us_trader` 하위만 받는다. blob filter + sparse-checkout 조합이 가장 효율적:

```bash
# 클론 위치: /opt 권장 (root 운영) 또는 ~/ (전용 사용자)
cd /opt   # 또는 cd ~

# 1) 최소 정보로 clone (실제 blob은 sparse 설정 후 받음)
git clone --depth 1 --filter=blob:none --sparse <YOUR_REPO_URL> kis_us_trader_repo

cd kis_us_trader_repo

# 2) kis_us_trader 폴더만 sparse 등록
git sparse-checkout set auth_ai/kis_us_trader

# 3) 결과 확인 — auth_ai 외 폴더는 받아지지 않음
ls -la
ls auth_ai/kis_us_trader

# 4) 작업 디렉터리로 이동
cd auth_ai/kis_us_trader
```

> Private repo면 SSH deploy key 또는 GitHub PAT 사용. 가능하면 deploy key 권장(read-only로 발급).

### 3.3 가상환경 + 의존성
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.4 .env 전송 (로컬 PC에서)
```bash
# 로컬에서 (반드시 scp 등 암호화 전송)
scp .env user@<VM_PUBLIC_IP>:~/kis_us_trader_repo/auth_ai/kis_us_trader/.env
```
VM 측에서:
```bash
chmod 600 .env  # 본인만 읽기
```

> ⚠️ git에 절대 커밋 금지(`.gitignore`로 차단되어 있음 — 그대로 두면 됨).

### 3.5 NTP 확인
```bash
timedatectl status
# 출력에 "NTP service: active" / "System clock synchronized: yes" 확인
```
> KIS 토큰 만료가 시간 의존이므로 시계 오차 1분 이내 권장.

### 3.6 잔고 API로 IP 등록 검증 (시간대 무관)
```bash
python test/test_balance_parse.py
```
- `rt_cd: "0"` 이면 KIS IP 등록 성공.
- `rt_cd: "1"` + IP 관련 메시지면 KIS Developers 갱신이 아직 승인 안 됐거나 잘못된 IP를 등록.

### 3.7 systemd 서비스 등록 (자동 시작 + 자동 재시작)

> ⚠️ `Environment=PYTHONUNBUFFERED=1`은 **필수**. 없으면 Python stdout이 파일로 리다이렉트될 때 block-buffered가 되어 `logs/daily_trader.out`에 출력이 즉시 안 쌓인다(약 4KB 버퍼가 찰 때까지 대기). 사이클이 하루 1회라 사실상 며칠치가 한 번에 flush됨 → tail로 운영 모니터링 불가.

```bash
sudo tee /etc/systemd/system/kis-trader.service > /dev/null <<'EOF'
[Unit]
Description=KIS US Trader daily cycle
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=/opt/kis_us_trader_repo/auth_ai/kis_us_trader
ExecStart=/opt/kis_us_trader_repo/auth_ai/kis_us_trader/.venv/bin/python daily_trader.py
Restart=on-failure
RestartSec=30
StandardOutput=append:/opt/kis_us_trader_repo/auth_ai/kis_us_trader/logs/daily_trader.out
StandardError=append:/opt/kis_us_trader_repo/auth_ai/kis_us_trader/logs/daily_trader.err

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kis-trader
```

> heredoc 본문이 들여쓰기되어 있어 그대로 복붙하면 bash `<<EOF`(non-`-`) 변형이 종료자 매치 실패로 멈춥니다. **실제 적용 시에는 heredoc 본문과 EOF를 들여쓰기 없이** 붙여 넣으세요. 위 마크다운 형식은 가독성 보존용입니다.

### 3.8 가동 확인
```bash
sudo systemctl status kis-trader
# Active: active (running) 확인

# 텔레그램에 "🚀 하루1회 자동매매 시작 (모의). 매일 07:30 KST 점검..." 메시지 도착 → 성공
```

---

## 4. 운영 시 주의점 6가지

### 4.1 KIS 토큰 캐시 보존
`~/.kis_us_trader/token_paper.json`이 액세스 토큰 캐시 파일. KIS는 **24시간마다 재발급 가능 횟수에 제한**이 있어, VM 디스크를 자주 갈아엎으면 토큰 발급 한도에 걸린다.
- 같은 VM/같은 디스크 유지 권장.
- Server Image(스냅샷) 만들 때 토큰 캐시 파일은 굳이 포함하지 않아도 됨 (24h 후 자연 재발급).

### 4.2 로그 디스크 가득참 방지
audit + systemd stdout 합쳐 연 100MB 미만이지만 안전망:
```bash
sudo tee /etc/logrotate.d/kis-trader > /dev/null <<EOF
/home/$USER/kis_us_trader_repo/auth_ai/kis_us_trader/logs/*.out
/home/$USER/kis_us_trader_repo/auth_ai/kis_us_trader/logs/*.err {
    weekly
    rotate 4
    compress
    missingok
    notifempty
}
EOF
```
`logs/cycles-YYYYMM.jsonl`는 월별 자동 분리되어 별도 로테이트 불필요.

### 4.3 `.env` 누출 방지
- `chmod 600 .env`
- 절대 git/이미지/스냅샷에 포함시키지 말 것.
- 네이버클라우드 콘솔 스크린샷 공유 시 `.env` 내용 안 비치게.
- 가능하면 네이버클라우드 **Secure Zone** 또는 **Cloud Key Management Service**(가격 부담되면 패스) 활용.

### 4.4 보안그룹 최소화
- 인바운드: SSH(22) 본인 IP에서만.
- 인바운드: 다른 모든 포트 차단 (텔레그램은 outbound long polling이라 인바운드 불필요).
- 아웃바운드: 전체 허용 (KIS/OpenAI/Telegram 호출).

### 4.5 백업 (선택)
- 주 1회 `.state/state.json`과 `logs/cycles-YYYYMM.jsonl`을 **Object Storage**에 업로드 권장 (Phase 4 포함).
- 또는 단순히 매일 자동 Server Image 스냅샷 (네이버클라우드 콘솔에서 스케줄 설정).

### 4.6 KIS API IP 재등록 트리거
다음 상황에서 KIS IP 재신청 필요:
- VM 종료 후 새 인스턴스로 마이그레이션 (고정 IP 안 따라가는 경우)
- 리전 변경
- VPC 변경
- 다른 클라우드/PC로 이전

→ **고정 IP 한 번 잘 잡으면 거의 발생 안 함**. 동적 IP면 매번 발생.

---

## 5. 클라우드 옵션 비교

| 옵션 | 월 비용 | 장점 | 단점 |
|---|---|---|---|
| **Naver Cloud Server Micro** | ₩15~25k | 한국 리전(낮은 지연), 원화 결제, KT/SKT/LG 망 양호 | KIS IP 갱신 1회 필요 |
| AWS Seoul t4g.nano | ₩7~12k | 더 저렴, 성숙한 에코시스템, IAM/AMI 도구 풍부 | 달러 결제, KIS IP 갱신 1회 |
| GCP Seoul e2-micro | ₩5~10k | always-free 티어 사용 가능(2026 정책 확인 필요) | 달러 결제, 학습 곡선 |
| 본인 PC 항상 켜두기 | 전기료 ₩5~10k | 추가 인프라 0, IP 변경 불필요 | 정전·재부팅·OS 업데이트로 사이클 누락 위험 |
| 라즈베리파이 4 24/7 | 일회성 ₩50k | 작고 조용, 전기료 미미 | 초기 셋업 시간, 가정 IP 안정성 의존 |

**한국 사용자 + KIS 정규장 의존 + 매일 1회 실행**: 네이버클라우드가 첫 번째 선택지로 자연스러움.

---

## 6. 이전 시점 — 언제 옮길 것인가

| 상황 | 권장 |
|---|---|
| Phase 0 검증 진행 중 (test_order/test_balance_parse/test_roundtrip) | **PC에서 마무리.** 클라우드 이전은 검증 끝난 후. |
| Phase 0 완료, daily_trader 단일 종목(AAPL) 운영 시작 | **이전 적기.** 24/7 안정성 + 정전 방지 + 깔끔한 분리. |
| Phase 1+ 다종목 가동 | **반드시 클라우드.** PC 의존하면 사이클 누락 위험 커짐. |

**이유**: 검증 단계는 코드/설정 수정이 잦아 PC가 편리. 검증 끝나면 코드는 거의 안 바뀌고 안정성이 주요 관심사가 되므로 클라우드로 이전.

---

## 7. 트러블슈팅

### 7.1 `rt_cd=1` + "유효하지 않은 IP 입니다"
→ KIS Developers IP 등록이 VM의 현재 공인 IP와 불일치. 고정 IP 할당 + KIS 재등록.

```bash
# VM에서 현재 공인 IP 확인
curl -s ifconfig.me
```

### 7.2 systemd 서비스가 30초마다 재시작
→ `sudo journalctl -u kis-trader -n 100`로 에러 확인. 흔한 원인:
- `.env` 누락 (`Telegram 토큰 없음` 에러)
- `python-telegram-bot` 미설치 (`pip install -r requirements.txt` 재실행)
- KIS 토큰 발급 한도 초과 (24시간 대기)

### 7.3 텔레그램 메시지 안 옴
- VM에서 outbound 443 열려 있나? (기본은 열림)
- `.env`의 `TELEGRAM_BOT_TOKEN`이 정확한가
- 봇과 대화창에서 메시지 한 번 보내둔 적이 있나 (`/start`)

### 7.4 사이클이 발화 안 함 (07:30 KST에 아무 일도 안 일어남)
- `timedatectl status` → 시계 KST이고 NTP sync OK인지 확인
- `sudo systemctl status kis-trader` → Active 인지
- `tail -f logs/daily_trader.out` → "다음 실행까지 X.X시간 대기..." 메시지 확인

### 7.5 토큰 발급 한도 초과
→ 24시간 안에 KIS 토큰 발급을 너무 많이 시도하면 일시 잠금. 자동 재발급 트리거를 줄이고 24h 대기. `~/.kis_us_trader/token_paper.json` 보존 + VM 디스크 유지로 예방.

---

## 8. 가벼운 작업 보완 권장 (선택)

클라우드 운영 안정성을 위해 다음 작업을 Phase 1~4 사이에 끼워 넣으면 좋음:

| 작업 | Phase | 효과 |
|---|---|---|
| audit log/state.json 주 1회 Object Storage 백업 | Phase 4 | VM 손상 시 복구 가능 |
| 매일 자동 스냅샷 (네이버클라우드 콘솔) | Phase 1 즉시 | 1-click 복구 |
| `consecutive_errors ≥ 3`일 때 텔레그램 긴급 알림 | Phase 4 | 무인 운영 안정성 |
| 매 사이클 시작 시 "💓 heartbeat" 메시지 (옵션) | Phase 1 | 사이클 정상 발화 가시화 |
| Cloud Insight로 CPU/메모리 모니터링 | Phase 4 | 비용 최적화 |

대부분은 `Phase 4 — 운영 강화` 섹션에 자연스럽게 포함됨 ([DESIGN.md §5 Phase 4](./DESIGN.md) 참고).

---

## 9. 요약 체크리스트

이 가이드 따라 마이그레이션 완료 = 다음 9개 전부 ✅

- [ ] 네이버클라우드 VM 생성 (Micro, Ubuntu 22.04, 30GB SSD)
- [ ] **공인 IP 고정 할당**
- [ ] **KIS Developers에서 IP 변경 신청·승인**
- [ ] Python 3.11 + git + 가상환경 + `pip install -r requirements.txt`
- [ ] `.env` scp 전송 + `chmod 600`
- [ ] `python test/test_balance_parse.py` → `rt_cd=0`
- [ ] systemd `kis-trader.service` 등록 + enable
- [ ] 텔레그램 시작 메시지 도착 확인
- [ ] 다음 07:30 KST 사이클 정상 발화 확인 (1일 후)
