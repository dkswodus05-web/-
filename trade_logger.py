"""모든 신호·주문·에러를 콘솔과 trades.log 파일에 기록."""
import os
import sys
import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.log")

# Windows 작업 스케줄러로 실행하면 콘솔이 cp949 등 구식 코드페이지라
# 이모지(📊 등) 출력 시 UnicodeEncodeError로 프로그램이 죽는 문제를 방지.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        # 그래도 안 되면 콘솔 출력만 안전하게 대체하고 파일 기록은 원본대로 유지
        print(line.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
