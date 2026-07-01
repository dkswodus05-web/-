"""
실행 결과(신호/지표/로그)를 GitHub Gist에 올려서, 로컬의 algotu_ide.html이
Railway를 열어보지 않고도 브라우저에서 바로 최신 상태를 볼 수 있게 한다.

Railway의 Cron 컨테이너는 실행이 끝나면 사라지기 때문에, 결과를 어딘가
남에게 보여줄 수 있는 곳에 올려둬야 한다 — 그 역할을 하는 파일.

필요 환경변수: GITHUB_TOKEN (gist 스코프만 있으면 됨, repo 권한 불필요)
⚠️ 안전 원칙: 토큰이 없으면 조용히 건너뛴다 (전체 파이프라인이 이것 때문에
   실패하면 안 됨 — 상태 공유는 부가 기능일 뿐).
"""
import os
import json
import urllib.request
import urllib.error

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_DESC = "signal-invest-pro-status (자동 생성 — algotu_ide.html 연동용, 직접 수정하지 마세요)"


def _api(method, path, body=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "signal-invest-pro",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _find_gist_id():
    try:
        gists = _api("GET", "/gists")
    except Exception:
        return None
    for g in gists:
        if g.get("description") == GIST_DESC:
            return g["id"]
    return None


def publish(signal_json_str=None, indicators_json_str=None, trades_log_tail=None):
    """
    각 인자는 문자열(파일 내용) 그대로 전달. 실패해도 예외를 던지지 않고 None 반환
    (상태 공유가 안 되더라도 매매 파이프라인 본체는 계속 돌아야 하므로).
    반환값: 성공 시 gist id, 실패/미설정 시 None. 결과는 trade_logger로 로그를 남긴다
    (성공/실패 원인을 trades.log에서 바로 확인할 수 있도록).
    """
    try:
        from trade_logger import log
    except Exception:
        log = print

    if not GITHUB_TOKEN:
        log("ℹ️ GITHUB_TOKEN 없음 — IDE 연동(Gist 공유) 건너뜀 (매매엔 영향 없음)")
        return None

    files = {}
    if signal_json_str:
        files["signal.json"] = {"content": signal_json_str}
    if indicators_json_str:
        files["indicators.json"] = {"content": indicators_json_str}
    if trades_log_tail:
        files["trades.log"] = {"content": trades_log_tail}
    if not files:
        log("ℹ️ Gist에 올릴 내용이 없어 건너뜀")
        return None

    try:
        gid = _find_gist_id()
        body = {"description": GIST_DESC, "public": True, "files": files}
        if gid:
            _api("PATCH", f"/gists/{gid}", body)
        else:
            created = _api("POST", "/gists", body)
            gid = created.get("id")
        log(f"☁️ 상태 Gist 갱신 완료: https://gist.github.com/{gid}")
        return gid
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = ""
        log(f"⚠️ Gist 업로드 실패 (HTTP {e.code}) — GITHUB_TOKEN 권한(gist 스코프)을 확인하세요. {detail}")
        return None
    except Exception as e:
        log(f"⚠️ Gist 업로드 실패: {e}")
        return None
