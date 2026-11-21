"""민원 분석 파이프라인 (분류 → 세부 유형 → 필수 정보 판정 → 접수 채널 → 안내문)

    python3 analyze.py "집 앞 도로에 불법주차가 너무 많아요"
    python3 analyze.py "..." --json          # 결과 JSON 전체 출력
    python3 analyze.py "..." --no-tuned      # 튜닝 모델 대신 HCX-003 + 프롬프트로 분류 (튜닝 장애 시 백업)

같은 폴더에 필요한 파일:
    mapping.json              8개 분야 → 원본 18개 분야
    required_fields_18.json   팀원 작성 필수 정보 기준표 (18개)
    guide_db.json             접수 채널·팁
    fewshot_subcategory.json  (선택) 세부 유형 예시
    .env                      CLOVASTUDIO_API_KEY=nv-...

FastAPI 에서는  from analyze import analyze  →  analyze(text) 를 그대로 /analyze 응답으로 쓰면 된다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
HOST = "https://clovastudio.stream.ntruss.com"
BASE_MODEL = "HCX-003"

# ---------------------------------------------------------------- 설정·데이터 로드
def _load_env():
    p = HERE / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))

_load_env()
TUNED_TASK_ID = os.environ.get("TUNED_TASK_ID", "k6n4aqqb")   # minwon_cls_v1 (HCX-003, 2026-11-20). .env 로 교체 가능
MAPPING = json.loads((HERE / "mapping.json").read_text(encoding="utf-8"))            # {분야: [원본...]}
RULES = json.loads((HERE / "required_fields_18.json").read_text(encoding="utf-8"))  # 팀원 기준표
GUIDE = json.loads((HERE / "guide_db.json").read_text(encoding="utf-8"))
_fs = HERE / "fewshot_subcategory.json"
FEWSHOT_SUB = json.loads(_fs.read_text(encoding="utf-8")) if _fs.exists() else {}
LABELS = list(MAPPING.keys())
SUB_TO_CAT = {sub: cat for cat, subs in MAPPING.items() for sub in subs}

CLASSIFY_SYSTEM = (HERE / "system_prompt.txt").read_text(encoding="utf-8").strip() if (HERE / "system_prompt.txt").exists() else (
    "당신은 지방자치단체 민원 분류 담당자입니다. 민원 내용을 읽고 아래 8개 분야 중 하나로만 답하세요.\n"
    f"분야: {', '.join(LABELS)}\n답은 분야 이름만 출력합니다.")


# ---------------------------------------------------------------- HCX 호출
def _hcx(system: str, user: str, task: str | None = None, max_tokens: int = 400, temperature: float = 0.1) -> str:
    key = (os.environ.get("CLOVASTUDIO_API_KEY") or os.environ.get("NCP_CLOVASTUDIO_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("CLOVASTUDIO_API_KEY 또는 NCP_CLOVASTUDIO_API_KEY 가 없습니다 (.env)")
    url = f"{HOST}/v2/tasks/{task}/chat-completions" if task else f"{HOST}/v1/chat-completions/{BASE_MODEL}"
    headers = {"Authorization": key if key.startswith("Bearer ") else f"Bearer {key}",
               "X-NCP-CLOVASTUDIO-REQUEST-ID": uuid.uuid4().hex, "Content-Type": "application/json"}
    body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "maxTokens": max_tokens, "temperature": temperature, "topP": 0.8, "topK": 0, "repeatPenalty": 1.1}
    for attempt in range(3):
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code in (429,) or r.status_code >= 500:
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code != 200:
            raise RuntimeError(f"HCX {r.status_code}: {r.text[:200]}")
        return r.json()["result"]["message"]["content"].strip()
    raise RuntimeError("HCX 재시도 초과")


def _extract_json(text: str) -> dict:
    """응답에서 첫 번째 { ... } 블록을 꺼내 파싱 (코드펜스·설명문 섞여도 처리)"""
    text = re.sub(r"```(?:json)?", "", text)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"JSON 없음: {text[:120]}")
    return json.loads(m.group(0))


def _match_label(answer: str, candidates: list[str]) -> str | None:
    norm = lambda s: re.sub(r"[\s·•ㆍ\"'.,_/]", "", s)
    a = norm(answer)
    for c in candidates:
        if norm(c) in a:
            return c
    return None


# ---------------------------------------------------------------- 1) 8개 분야 분류
def classify(text: str, use_tuned: bool = True) -> dict:
    raw = _hcx(CLASSIFY_SYSTEM, text, task=TUNED_TASK_ID if use_tuned else None, max_tokens=20, temperature=0.01)
    label = _match_label(raw, LABELS)
    return {"category": label, "raw": raw, "model": f"tuned:{TUNED_TASK_ID}" if use_tuned else BASE_MODEL}


# ---------------------------------------------------------------- 2) 세부 유형 (원본 18개 중, 해당 분야에 속한 것만)
SUBTYPE_SYSTEM = """당신은 지방자치단체 민원 담당자입니다. 민원이 아래 세부 유형 중 어디에 해당하는지 하나만 고르세요.

세부 유형과 설명:
{options}

{examples}
또한 민원의 성격을 판단하세요.
- "신고": 현장의 문제·불편·위험을 알리고 조치(단속·수거·수리·점검)를 바라는 것
- "문의": 절차·방법·자격·일정·비용 등을 질문하는 것

반드시 아래 JSON 형식으로만 답하세요. 다른 말은 쓰지 마세요.
{{"subtype": "<세부 유형 이름>", "intent": "신고|문의", "reason": "<한 문장>"}}"""

SUBTYPE_DESC = {
    "자동차": "불법주정차, 주차단속, 차량 등록·이전, 차량 자체 문제",
    "교통": "신호등, 교차로, 버스·택시 등 대중교통, 노선, 교통 흐름",
    "안전건설": "도로·보도 파손, 공사장, 옹벽, 가로등 등 시설물 안전",
    "건축허가": "건축물 신축·증축·용도변경, 옥외광고물, 불법 건축",
    "토지": "지번·경계·측량·지적, 토지 이용",
    "환경미화": "쓰레기 투기·수거, 악취, 미세먼지, 재활용, 폐기물",
    "위생": "식당·업소 위생, 식품, 공중위생업소",
    "상하수도": "누수, 단수, 수압, 하수 역류, 수도 요금",
    "산림": "가로수·수목, 공원·놀이터·등산로 등 공원시설 관리, 산림 훼손 (공원 내 쓰레기·시설 문제 포함)",
    "농업_축산": "작물·가축·농지·축사, 농업 지원, 동물 등록",
    "복지": "복지 급여·돌봄·지원사업, 아동·노인·장애인 복지",
    "보건소": "예방접종, 검진, 보건증, 의료기관 신고, 보건소 이용",
    "세무": "지방세(재산세·자동차세·취득세 등), 과태료 납부, 세금 문의",
    "행정": "증명서 발급, 여권, 주민등록, 처리 지연, 공무원 응대",
    "공통": "특정 분야로 보기 어려운 일반 진정·건의·제안",
    "정보통신": "공공 홈페이지·앱 오류, 통신 설비",
    "경제": "소상공인·일자리·지역경제 지원사업, 시장, 상거래",
    "문화_체육_관광": "문화·체육시설, 행사, 관광지, 숙박업",
}


def classify_subtype(text: str, category: str) -> dict:
    cands = MAPPING[category]
    options = "\n".join(f"- {c}: {SUBTYPE_DESC.get(c, '')}" for c in cands)
    ex_lines = []
    for c in cands:
        for sub, texts in list(FEWSHOT_SUB.get(c, {}).items())[:2]:
            if texts:
                ex_lines.append(f'민원: {texts[0]}\n→ {{"subtype": "{c}"}}')
    examples = ("예시:\n" + "\n".join(ex_lines[:6]) + "\n") if ex_lines else ""
    raw = _hcx(SUBTYPE_SYSTEM.format(options=options, examples=examples), text, max_tokens=150)
    try:
        d = _extract_json(raw)
        sub = _match_label(str(d.get("subtype", "")), cands) or cands[0]
        intent = "문의" if "문의" in str(d.get("intent", "")) else "신고"
        return {"subtype": sub, "intent": intent, "reason": d.get("reason", ""), "raw": raw}
    except Exception:
        intent = "문의" if re.search(r"(나요|가요|까요|하죠|어떻게|뭐가|얼마나|궁금)", text) else "신고"
        return {"subtype": _match_label(raw, cands) or cands[0], "intent": intent, "reason": "", "raw": raw}


# ---------------------------------------------------------------- 3) 필수 정보 판정 (팀원 기준표 + HCX)
FIELDS_SYSTEM = """당신은 지방자치단체 민원 접수 담당자입니다. 민원 원문을 읽고, 아래 각 항목이 원문에 충분히 들어 있는지 판정하세요.

판정 기준:
- sufficient: 항목의 check 기준을 원문이 충족함
- insufficient: 언급은 있지만 check 기준에 못 미침 (예: "집 앞"처럼 위치가 막연함)
- missing: 원문에 전혀 없음
- not_applicable: when 조건에 해당하지 않아 검사 대상이 아님

규칙:
1. 원문에 없는 내용을 추측해서 채우지 마세요. value 에는 원문에서 찾은 표현을 그대로 적고, 없으면 null.
2. 조금이라도 언급이 있으면 missing 이 아니라 insufficient 입니다. missing 은 전혀 언급이 없을 때만.
3. "3일째", "일주일째", "밤마다", "어제부터" 같은 상대적 시간 표현도 일시 정보로 인정합니다 (sufficient 또는 insufficient).
4. when 조건이 있는 항목은, 민원이 그 조건에 해당하지 않으면 반드시 not_applicable 로 판정합니다.
5. 이 민원의 성격은 "{intent}"입니다. 문의(절차·방법·자격·일정 질문)인 경우 발생 위치·일시·현장 상황·피해 규모 같은 현장 항목은 not_applicable 로 판정합니다.
6. 신청인의 이름·연락처는 검사하지 않습니다.

검사 항목 (세부 유형: {subtype}):
{fields}

반드시 아래 JSON 형식으로만 답하세요.
{{"fields": [{{"key": "...", "status": "sufficient|insufficient|missing|not_applicable", "value": "원문 표현 또는 null", "note": "부족하면 무엇이 더 필요한지 한 문장"}}]}}"""


def check_fields(text: str, subtype: str, intent: str = "신고") -> dict:
    spec = RULES["categories"].get(subtype, {}).get("required_fields", [])
    if not spec:
        return {"fields": [], "raw": ""}
    lines = []
    for f in spec:
        when = f" (when: {f['when']})" if f.get("when") else ""
        lines.append(f"- key={f['key']} / {f['label']}{when}\n  check: {f['check']}")
    raw = _hcx(FIELDS_SYSTEM.format(subtype=subtype, fields="\n".join(lines), intent=intent), text, max_tokens=600)
    try:
        d = _extract_json(raw)
        by_key = {x.get("key"): x for x in d.get("fields", [])}
        fields = []
        for f in spec:                       # 기준표 순서·라벨을 기준으로 정리
            x = by_key.get(f["key"], {})
            st = x.get("status", "missing")
            if st not in ("sufficient", "insufficient", "missing", "not_applicable"):
                st = "missing"
            fields.append({"key": f["key"], "label": f["label"], "status": st,
                           "value": x.get("value"), "note": x.get("note", "")})
        return {"fields": fields, "raw": raw}
    except Exception as e:
        return {"fields": [{"key": f["key"], "label": f["label"], "status": "missing", "value": None,
                            "note": f"판정 실패: {e}"} for f in spec], "raw": raw}


# ---------------------------------------------------------------- 4) 채널 조회 + 안내문 조립 (LLM 없음)
def _josa(word: str, pair: str) -> str:
    """받침 유무로 조사 선택. pair: '이가' | '을를' | '은는'"""
    if not word:
        return pair[1]
    code = ord(word[-1])
    has_batchim = 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0
    return pair[0] if has_batchim else pair[1]

EMERGENCY_PATTERNS = [
    (r"(불이|화재|불났|연기가|타는 냄새)", "119"),
    (r"(가스 ?냄새|가스가 새|누출)", "119"),
    (r"(폭행|때리|흉기|칼|위협|스토킹|납치|실종|사라졌)", "112"),
    (r"(쓰러져|의식이 없|숨을 안|호흡이|피를 흘)", "119"),
    (r"(며칠째 (안 보|연락이 안)|고독사|혼자 사시는.*안 보)", "129"),
]
EMERGENCY_NOTE = {
    "119": "화재·가스·구급 상황이면 지금 바로 119로 전화하세요.",
    "112": "범죄·위협·실종 상황이면 지금 바로 112로 전화하세요.",
    "129": "이웃의 안전이 걱정되면 보건복지상담센터 129 또는 112로 바로 연락하세요. 복지 위기 신고로 접수됩니다.",
}


def check_emergency(text: str) -> dict | None:
    for pat, num in EMERGENCY_PATTERNS:
        if re.search(pat, text):
            return {"number": num, "note": EMERGENCY_NOTE[num]}
    return None


def build_guide(category: str, subtype: str, fields: list[dict], intent: str = "신고", emergency: dict | None = None) -> dict:
    sub = GUIDE["subtypes"].get(subtype, {})
    keys = sub.get("channels_inquiry") if intent == "문의" and sub.get("channels_inquiry") else sub.get("channels", ["epeople"])
    channels = [dict(GUIDE["channels"][k], key=k) for k in keys]
    missing = [f for f in fields if f["status"] == "missing"]
    insufficient = [f for f in fields if f["status"] == "insufficient"]

    suggestions = []
    for f in missing:
        suggestions.append(f"'{f['label']}'{_josa(f['label'], '이가')} 없습니다. " + (f["note"] or "내용을 추가해 주세요."))
    for f in insufficient:
        suggestions.append(f"'{f['label']}'{_josa(f['label'], '을를')} 더 구체적으로 적어주세요. " + (f["note"] or ""))
    if sub.get("tip"):
        suggestions.append("팁: " + sub["tip"])

    main = channels[0] if channels else None
    parts = []
    if emergency:
        parts.append("⚠ " + emergency["note"])
    parts.append(f"이 민원은 '{category}' 분야의 '{subtype}' 유형({intent})으로 보입니다.")
    if missing or insufficient:
        names = [f["label"] for f in missing] + [f["label"] for f in insufficient]
        parts.append("접수 전에 " + ", ".join(names) + " 정보를 보완해 주세요.")
    else:
        parts.append("필요한 정보가 잘 갖춰져 있습니다.")
    if main:
        how = f" {main['how']}" if main.get("how") else ""
        tel = f" 전화는 {main['phone']}입니다." if main.get("phone") else ""
        parts.append(f"접수는 {main['name']}에서 하시면 됩니다.{how}{tel}")
    guide_text = " ".join(parts)

    return {"intent": intent, "emergency": emergency,
            "channels": [{k: c.get(k, "") for k in ("key", "name", "url", "app", "phone", "how", "verified")} for c in channels],
            "missing": [f["label"] for f in missing], "insufficient": [f["label"] for f in insufficient],
            "suggestions": suggestions, "guide_text": guide_text}


# ---------------------------------------------------------------- 전체
MIN_CONTENT_CHARS = 8   # 공백·문장부호 뺀 글자 수가 이보다 적으면 LLM 호출 없이 되묻기


def analyze(text: str, use_tuned: bool = True) -> dict:
    t0 = time.time()
    text = (text or "").strip()
    content = re.sub(r"[\s\.,!?~…]", "", text)
    if len(content) < MIN_CONTENT_CHARS or re.fullmatch(r"(도와주세요|도와줘|살려주세요|안녕하세요|문의요|신고요)[\s\.!]*", text):
        return {"text": text, "category": None, "subtype": None, "intent": None, "fields": [], "channels": [],
                "missing": [], "insufficient": [], "emergency": check_emergency(text),
                "suggestions": ["무엇이, 어디서, 언제 문제인지 한두 문장으로 적어주세요. (예: 성산구 ○○동 ○○아파트 앞 횡단보도에 차가 주차돼 있어요)"],
                "guide_text": "민원 내용이 너무 짧아 분류할 수 없습니다. 무엇이, 어디서, 언제 문제인지 적어주시면 접수처와 필요한 정보를 안내해 드릴게요.",
                "_debug": {"reason": "too_short", "elapsed_sec": 0.0}}
    c = classify(text, use_tuned)
    if not c["category"]:
        return {"error": "분야를 판독하지 못했습니다", "raw": c["raw"]}
    s = classify_subtype(text, c["category"])
    f = check_fields(text, s["subtype"], s["intent"])
    g = build_guide(c["category"], s["subtype"], f["fields"], s["intent"], check_emergency(text))
    return {"text": text, "category": c["category"], "subtype": s["subtype"], "subtype_reason": s["reason"],
            "fields": f["fields"], **g,
            "_debug": {"classify_raw": c["raw"], "model": c["model"], "elapsed_sec": round(time.time() - t0, 1)}}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__); sys.exit(1)
    res = analyze(" ".join(args), use_tuned="--no-tuned" not in sys.argv)
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=2)); sys.exit(0)
    if "error" in res:
        print("오류:", res); sys.exit(1)
    if res["category"] is None:
        print("[안내문]", res["guide_text"]); sys.exit(0)
    if res.get("emergency"):
        print("\n⚠ 긴급:", res["emergency"]["note"])
    print(f"\n[분야] {res['category']}  >  [세부] {res['subtype']}  [{res['intent']}]  ({res['subtype_reason']})")
    print("[필수 정보]")
    for f in res["fields"]:
        mark = {"sufficient": "O", "insufficient": "△", "missing": "X", "not_applicable": "-"}[f["status"]]
        print(f"  {mark} {f['label']}: {f['value'] or ''}  {('— ' + f['note']) if f['note'] and mark != 'O' else ''}")
    print("[보완 제안]")
    for s in res["suggestions"]:
        print("  -", s)
    print("[접수 채널]")
    for ch in res["channels"]:
        print(f"  - {ch['name']} {ch['url']} {ch['phone']} {'' if ch['verified'] else '(미확인)'}")
    print("[안내문]", res["guide_text"])
    print(f"({res['_debug']['elapsed_sec']}초)")
