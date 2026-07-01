# 로컬 PC 자동 프로그램으로 독립시키기

> 지금까지는 Claude 데스크톱 앱(Cowork)이 켜져 있을 때만 매일 8시 스케줄이 돌았습니다.
> 이 가이드는 **Claude 앱과 무관하게, Windows 작업 스케줄러가 파이썬 프로그램을 직접 실행**하도록 바꾸는 절차입니다.
> PC가 켜져 있기만 하면 Claude 앱을 열지 않아도 매일 자동으로 돕니다.

---

## 무엇이 바뀌었나

기존에는 "AI 투자위원회(Bull/Bear/Judge)" 판단을 Claude 앱 세션이 대신 해줬습니다.
이제는 `ai_committee.py`가 **Anthropic API를 직접 호출**해서 같은 역할을 합니다.
그래서 새 API 키가 하나 더 필요합니다 (Alpaca, FRED와는 별개).

새로 추가된 파일:
| 파일 | 역할 |
|------|------|
| `ai_committee.py` | Bull/Bear/Judge를 Anthropic API로 직접 호출 (브라우저·Claude 앱 불필요) |
| `daily_pipeline.py` | 지표수집→AI위원회→signal.json→매매실행을 한 번에 실행하는 진입점 |
| `run_daily_pipeline.bat` | Windows 작업 스케줄러가 실행할 배치파일 |

---

## 1단계 — Anthropic API 키 발급 & 설치

1. https://console.anthropic.com/ 가입 → API Keys → 새 키 생성
2. `.env` 파일을 열어 채우기:
   ```
   ANTHROPIC_API_KEY=발급받은_키
   ```
3. 패키지 설치:
   ```
   pip install -r requirements.txt
   ```

> 참고: 하루 1회 호출이라 비용은 미미합니다 (건당 몇 원~수십 원 수준).

---

## 2단계 — 수동으로 한 번 테스트

프로젝트 폴더에서 더블클릭하거나 명령 프롬프트에서:
```
run_daily_pipeline.bat
```
`trades.log`와 `pipeline_stdout.log`를 열어 아래처럼 끝까지 도는지 확인:
```
📊 지표 수집: 17/17 (ok=True)
🐂 Bull: ...
🐻 Bear: ...
⚖️ Judge: BUY (확신도 75) — ...
🛡 리스크 게이트: ✅ 허용 — ...
🟢 매수 주문 전송: {'status': 'DRY_RUN', ...}
```
DRY_RUN=true인 동안은 실제 주문이 나가지 않고 시뮬 로그만 남습니다 (안전).

---

## 3단계 — Windows 작업 스케줄러에 등록

관리자 권한 없이 명령 프롬프트(cmd)에서 아래 한 줄을 실행하면 됩니다 (경로의 공백 때문에 따옴표 그대로 유지):

```cmd
schtasks /create /tn "SignalInvestDaily" /tr "\"C:\Users\jaeyeon\Desktop\해외주식 자동매매\run_daily_pipeline.bat\"" /sc weekly /d MON,TUE,WED,THU,FRI /st 08:00 /f
```

- 평일(월~금) 아침 8시에 `run_daily_pipeline.bat` 실행
- `/f`는 동일 이름 작업이 있으면 덮어씀

**등록 확인:**
```cmd
schtasks /query /tn "SignalInvestDaily" /v /fo LIST
```

**지금 바로 한 번 실행해서 스케줄러 경로로도 정상 도는지 확인:**
```cmd
schtasks /run /tn "SignalInvestDaily"
```
몇 초 후 `pipeline_stdout.log` / `trades.log`에 새 기록이 남으면 성공입니다.

**삭제하고 싶을 때:**
```cmd
schtasks /delete /tn "SignalInvestDaily" /f
```

> Windows "작업 스케줄러" 앱(GUI)에서도 "SignalInvestDaily"라는 이름으로 보이며, 여기서 시간 변경·비활성화도 가능합니다.

---

## 4단계 — 기존 Claude 앱 스케줄과 중복 정리 (중요)

지금 Cowork에는 `signal-invest-daily`라는 스케줄이 이미 등록돼 있어, **Claude 앱이 켜져 있으면 같은 파이프라인이 두 번 도는** 상태가 됩니다. DRY_RUN인 지금은 로그만 두 번 남는 정도라 크게 위험하지 않지만, 나중에 Paper/Live로 바꾸면 하루에 매수 주문이 두 번 나갈 수 있습니다.

로컬 프로그램이 정상 작동하는 걸 확인했다면, 기존 Cowork 스케줄은 꺼두는 걸 권합니다. 원하시면 제가 지금 바로 꺼드릴게요.

---

## 컴퓨터를 켜둘 수 없는 날은?

Windows 작업 스케줄러는 **그 시각에 PC가 켜져 있어야** 실행됩니다. 꺼져 있으면 그날은 건너뜁니다(에러 없이 조용히 안 돔). 완전히 무인으로 돌리려면 다음 단계인 **클라우드 서버 배포**로 넘어가면 됩니다 (PC 없이 24시간 자동 실행).

---

### 고지
본 프로젝트는 개인 학습·기록용입니다. 투자 권유가 아니며, 자동매매는 실제 손실을 낼 수 있습니다. 모든 판단과 책임은 본인에게 있습니다.
