"""앱에 넣어 두는 외부 서비스 키(OpenAQ: 전 세계 미세먼지 측정소, 에어코리아: 한국 측정소). 사용자가 입력하는 것이 아니라 **만든 사람의 키**를 쓴다.

- 키는 저장소(GitHub)에 올리지 않는다. 빌드할 때 만든 사람의 PC 에 있는 메모장(`dalu_api_keys.txt`, 홈 폴더)에서 읽어 설치 파일 안의 `app/service_keys.json` 으로 넣는다(installer/build_release.py).
- 앱은 `service_keys.json` 을 읽는다. 없으면(소스에서 바로 실행할 때는 홈 폴더의 메모장을 읽는다) 그 서비스는 쓰지 않고 예측 모델 값("추정")을 보여 준다.
- 키를 기록(log)하지 않고, 화면·설정 내보내기에도 나오지 않는다. 키는 요청 헤더/주소에만 쓰이고 사용자 정보는 담기지 않는다(PRIVACY.md).
"""
import json
import os
import re

NAMES = ("openaq", "airkorea")
_HERE = os.path.dirname(os.path.abspath(__file__))


def parse_notepad(text):
    """'OPENAQ=값' 줄을 읽는다(# 로 시작하는 줄과 빈 줄은 무시, 값의 앞뒤 공백·따옴표 제거) -> {'openaq': ..., 'airkorea': ...} (값이 있는 것만)."""
    out = {}
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = re.sub(r"[^a-z]", "", k.strip().lower())
        v = v.strip().strip("\"'").strip()
        if k in NAMES and v and len(v) <= 400 and not re.search(r"\s", v):
            out[k] = v
    return out


def load(app_dir=_HERE, home=None):
    """{'openaq': str, 'airkorea': str}: 설치된 앱의 service_keys.json, 없으면 홈 폴더의 메모장(만든 사람이 소스에서 실행할 때). 읽지 못하면 빈 값."""
    out = {n: "" for n in NAMES}
    try:
        with open(os.path.join(app_dir, "service_keys.json"), encoding="utf-8") as f:
            d = json.load(f)
        for n in NAMES:
            if isinstance(d.get(n), str):
                out[n] = d[n].strip()
        if any(out.values()):
            return out
    except Exception:
        pass
    try:
        with open(os.path.join(home or os.path.expanduser("~"), "dalu_api_keys.txt"), encoding="utf-8") as f:
            for k, v in parse_notepad(f.read()).items():
                out[k] = v
    except Exception:
        pass
    return out
