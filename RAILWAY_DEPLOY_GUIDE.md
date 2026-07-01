# Railway로 24시간 자동 실행하기 (PC 없이)

> 로컬 Windows 작업 스케줄러와 코드는 동일합니다. 실행 장소만 Railway 서버로 옮기는 작업입니다.
> `daily_pipeline.py`는 한 번 실행하고 끝나는 구조라 Railway의 "Cron Job" 서비스 방식과 정확히 맞습니다.

---

## 0. 배포 방법 두 가지 중 선택

| 방법 | 장점 | 단점 |
|------|------|------|
| A. Railway CLI로 폴더 직접 업로드 | 설정 빠름, GitHub 몰라도 됨 | 코드 수정할 때마다 `railway up` 수동 재실행 |
| **B. GitHub Desktop → GitHub → Railway 연동** | 코드 push하면 자동 재배포, 백업도 됨 | GitHub 계정/앱 설치가 한 단계 더 필요 |

GUI(마우스 클릭) 방식을 선호하시면 **B가 더 편합니다.** 아래는 B 기준입니다.

⚠️ **중요**: `.env` 파일에는 진짜 API 키가 들어있습니다. 이미 이 폴더에 `.gitignore`를 만들어뒀고, 여기에 `.env`가 포함돼 있어서 **GitHub Desktop이 자동으로 `.env`를 커밋 대상에서 제외**합니다. GitHub Desktop 화면에서 커밋 전 "Changes" 목록에 `.env`가 안 보이는지 꼭 확인하세요.

---

## 1. GitHub Desktop 설치 & 저장소 만들기

1. https://desktop.github.com 에서 설치 → GitHub 계정으로 로그인 (계정 없으면 이 김에 무료 가입)
2. GitHub Desktop 메뉴 **File → Add Local Repository** → 이 폴더(`C:\Users\jaeyeon\Desktop\해외주식 자동매매`) 선택
3. "이 폴더는 아직 Git 저장소가 아닙니다"라는 안내가 뜨면 **create a repository** 클릭
4. 왼쪽 하단에서 커밋 메시지(예: "초기 업로드") 입력 → **Commit to main**
   - 이때 변경 파일 목록에 `.env`가 없는지 한 번 더 확인 (있으면 취소하고 저에게 알려주세요)
5. 상단 **Publish repository** 클릭 → **꼭 "Keep this code private" 체크** (API 키 관련 코드라 비공개 권장) → Publish

---

## 2. Railway를 GitHub 저장소에 연결

1. railway.app 로그인 → **New Project → Deploy from GitHub repo**
2. 방금 만든 저장소 선택 → Railway가 자동으로 `requirements.txt`를 보고 파이썬 환경 구성
3. 이후 GitHub Desktop에서 코드를 고치고 **Commit → Push origin**만 하면, Railway가 자동으로 재배포합니다.

*(CLI 방식(A)을 쓰려면 대신 `npm install -g @railway/cli` → `railway login` → 이 폴더에서 `railway init` → `railway up`)*

---

## 3. 환경변수 등록 (Alpaca/FRED/Anthropic 키 + 설정)

Railway 대시보드(railway.app) → 방금 만든 프로젝트 → 서비스 클릭 → **Variables** 탭에서 아래를 하나씩 추가 (또는 CLI로):

```
railway variables --set "ALPACA_API_KEY=..." --set "ALPACA_SECRET_KEY=..." --set "FRED_API_KEY=..." --set "ANTHROPIC_API_KEY=..." --set "ANTHROPIC_MODEL=claude-sonnet-5" --set "DRY_RUN=true" --set "ACTIVE_SYMBOL=SPY"
```

⚠️ `DRY_RUN=true`는 그대로 두세요. 실거래 전환은 로컬에서 충분히 검증한 뒤에만.

---

## 4. Cron 스케줄 설정 (핵심)

대시보드 → 서비스 → **Settings**:
1. **Deploy → Custom Start Command**: `python daily_pipeline.py`
2. **Cron Schedule**: 아래 값 입력

```
0 23 * * 0-4
```

Railway의 Cron은 **UTC 기준**입니다. 한국시간 평일 아침 8시 = UTC 기준 (전날) 23시라서, 요일도 하루씩 당겨 `0-4(일~목)`로 지정하면 결과적으로 한국시간 월~금 오전 8시에 실행됩니다.

설정 후 서비스는 그 시각에만 컨테이너를 켜서 한 번 실행하고 끝나면 자동으로 종료합니다 — 계속 켜져 있는 게 아니라서 비용도 절약됩니다.

---

## 5. 확인

- Railway 대시보드 → **Deployments/Logs** 탭에서 실행 로그 확인 (trade_logger의 출력이 그대로 보임)
- `trades.log`는 컨테이너 안에만 남고 재시작하면 사라집니다 — 영구 기록이 필요하면 나중에 Railway Volume을 붙이거나, 텔레그램 알림(로드맵의 확장 항목)으로 결과를 폰으로 받는 걸 추천합니다.

---

## 6. 로컬 Task Scheduler는 어떻게 하나

Railway가 정상적으로 돌기 시작하면, 로컬 PC의 `SignalInvestDaily` 작업은 **중복 실행 방지를 위해 꺼두세요**:
```
schtasks /delete /tn "SignalInvestDaily" /f
```
그리고 Cowork의 기존 스케줄(`signal-invest-daily`)도 함께 꺼야 하루에 신호가 한 번만 만들어집니다.

---

### 참고: 비용
Railway는 가입 시 소액의 무료 크레딧을 제공하고, 이후로는 사용량(실행 시간) 기준으로 과금됩니다. 하루 1회, 몇 분이면 끝나는 작업이라 비용은 매우 적을 것으로 예상되지만, 정확한 현재 요금은 railway.com/pricing에서 직접 확인하세요.

## 7. IDE를 아무나(모바일 포함) 볼 수 있는 웹페이지로 호스팅하기

`index.html`(기존 `algotu_ide.html`)을 매번 로컬에서 열고 Gist 주소를 연동할 필요 없이, 아예 공개된 웹 주소 하나로 접속해서 보게 만드는 방법입니다. 이미 만든 Railway 프로젝트에 **서비스를 하나 더** 추가하는 것뿐이라 새 계정이나 별도 설정 없이 됩니다.

1. Railway 프로젝트(예: `romantic-empathy`) 화면에서 **+ New → GitHub Repo** → 지금 쓰고 있는 저장소(예: `dkswodus05-web/-`) 다시 선택
   - 같은 저장소를 가리키는 **두 번째 서비스**가 생깁니다 (하나는 매매 파이프라인용 Cron, 하나는 이 화면 호스팅용)
2. 새로 생긴 서비스 → **Settings → Deploy → Custom Start Command**에 입력:
   ```
   python -m http.server $PORT
   ```
3. 같은 Settings 화면의 **Networking**에서 **Generate Domain** 클릭 → `xxxx.up.railway.app` 같은 공개 주소가 생깁니다
4. ⚠️ 이 새 서비스에는 **Cron Schedule을 넣지 마세요** — 매매용이 아니라 항상 켜져 있는 화면용이라, 그냥 웹 서비스로 계속 떠 있어야 합니다
5. 생성된 주소로 접속하면 `index.html`이 바로 뜨고, Gist 주소가 코드에 이미 기본값으로 박혀 있어서 **연동 버튼을 누를 필요 없이** 바로 오늘의 신호가 보입니다. PC·휴대폰 아무 브라우저에서나 그 주소만 열면 됩니다.

**참고**: 이 주소는 로그인 없이 링크만 있으면 누구나 볼 수 있습니다. DRY_RUN 데모 데이터(가짜 $100,000 계좌, 신호·근거 로그)만 보이고 실제 돈·개인정보는 노출되지 않지만, 링크를 굳이 여기저기 공유할 필요는 없다는 점만 유의하세요.

---

### 고지
본 프로젝트는 개인 학습·기록용입니다. 투자 권유가 아니며, 자동매매는 실제 손실을 낼 수 있습니다. 모든 판단과 책임은 본인에게 있습니다.
