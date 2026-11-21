"""민원 8개 분야 분류 평가 — 튜닝 전(베이스 HCX-003) / 튜닝 후(작업 ID) 를 같은 test.jsonl 로 측정

사용법 (서버 ~/team_proj 에서, test.jsonl · system_prompt.txt 가 같은 폴더에 있다고 가정):

    # 1) 튜닝 전 베이스라인 (HCX-003 + 같은 시스템 프롬프트)
    python3 eval_classifier.py --model HCX-003 --tag base

    # 2) 튜닝 후 (학습 완료된 작업 ID)
    python3 eval_classifier.py --task k6n4aqqb --tag tuned

    # 3) 두 결과 비교표
    python3 eval_classifier.py --compare base tuned

옵션:
    --limit 40      앞 40건만 빠르게 (처음엔 이걸로 호출이 되는지 확인)
    --dry-run       API 호출 없이 URL·본문만 출력
    --fewshot N     시스템 프롬프트 뒤에 train.csv 예시 N개를 붙여서 평가 (프롬프트만으로 어디까지 되는지 비교용)

API 키: 환경변수 CLOVASTUDIO_API_KEY 또는 같은 폴더 .env 의 CLOVASTUDIO_API_KEY=... (Bearer 없이 키만)
결과: results/<tag>.jsonl (문항별 응답, 중단돼도 이어서 실행), results/<tag>_summary.md
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import requests

HOST = "https://clovastudio.stream.ntruss.com"
HERE = Path(__file__).resolve().parent


def load_env():
    p = HERE / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def api_key() -> str:
    key = os.environ.get("CLOVASTUDIO_API_KEY", "").strip()
    if not key:
        sys.exit("CLOVASTUDIO_API_KEY 가 없습니다. 환경변수나 .env 에 넣어주세요.")
    return key if key.startswith("Bearer ") else f"Bearer {key}"


def endpoint(model: str | None, task: str | None) -> str:
    if task:
        return f"{HOST}/v2/tasks/{task}/chat-completions"   # HCX-003 튜닝 모델
    return f"{HOST}/v1/chat-completions/{model}"           # 베이스 모델 (HCX-003 등)


def call(url: str, system: str, user: str, dry: bool = False) -> str:
    body = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "maxTokens": 20, "temperature": 0.01, "topP": 0.8, "topK": 0, "repeatPenalty": 1.2,
    }
    if dry:
        print("POST", url); print(json.dumps(body, ensure_ascii=False, indent=1)); return ""
    headers = {"Authorization": api_key(), "X-NCP-CLOVASTUDIO-REQUEST-ID": uuid.uuid4().hex,
               "Content-Type": "application/json"}
    for attempt in range(4):
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
        data = r.json()
        return data["result"]["message"]["content"].strip()
    raise RuntimeError("재시도 초과 (429/5xx)")


def normalize(answer: str, labels: list[str]) -> str | None:
    """모델 응답에서 분야 이름을 찾아낸다. 가운뎃점·공백·따옴표 차이는 무시."""
    def key(s): return re.sub(r"[\s·•ㆍ\"'.,]", "", s)
    a = key(answer)
    for lab in labels:                      # 정확히 포함
        if key(lab) in a:
            return lab
    for lab in labels:                      # 앞부분만 (예: "교통" → 교통·자동차)
        if key(lab).split("·")[0][:2] in a:
            return lab
    return None


def fewshot_block(n: int) -> str:
    p = HERE / "train.csv"
    if n <= 0 or not p.exists():
        return ""
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    per = collections.defaultdict(list)
    for r in rows:
        per[r["Completion"]].append(r["Text"])
    ex = []
    i = 0
    while len(ex) < n:
        for lab, texts in per.items():
            if i < len(texts) and len(ex) < n:
                ex.append(f"민원: {texts[i]}\n분야: {lab}")
        i += 1
    return "\n\n예시:\n" + "\n\n".join(ex)


def evaluate(args):
    test = [json.loads(l) for l in open(HERE / "test.jsonl", encoding="utf-8")]
    if args.limit:
        test = test[: args.limit]
    labels = list(dict.fromkeys(r["label"] for r in json.loads("[" + ",".join(
        l for l in open(HERE / "test.jsonl", encoding="utf-8")) + "]")))
    system = (HERE / "system_prompt.txt").read_text(encoding="utf-8").strip() + fewshot_block(args.fewshot)
    url = endpoint(args.model, args.task)
    out_dir = HERE / "results"; out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{args.tag}.jsonl"

    done = {}
    if out_path.exists() and not args.restart:
        for l in open(out_path, encoding="utf-8"):
            r = json.loads(l); done[r["id"]] = r
    print(f"[{args.tag}] {url}\n  문항 {len(test)}건, 이미 완료 {len(done)}건, few-shot {args.fewshot}개")
    if args.dry_run:
        call(url, system, test[0]["text"], dry=True); return

    with open(out_path, "a", encoding="utf-8") as f:
        for i, r in enumerate(test, 1):
            if r["id"] in done:
                continue
            try:
                raw = call(url, system, r["text"])
            except Exception as e:
                print(f"  [{i}] 오류: {e}"); time.sleep(3); continue
            pred = normalize(raw, labels)
            rec = {**r, "raw": raw, "pred": pred, "correct": pred == r["label"]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            done[r["id"]] = rec
            mark = "O" if rec["correct"] else ("X" if pred else "?")
            print(f"  [{i}/{len(test)}] {mark} {r['label']} ← {raw[:30]!r}")
            time.sleep(args.sleep)
    summarize(args.tag, list(done.values()), labels, url, system)


def summarize(tag, recs, labels, url="", system=""):
    n = len(recs); correct = sum(r["correct"] for r in recs)
    fmt_ok = sum(1 for r in recs if r["pred"] is not None)
    exact = sum(1 for r in recs if r["raw"].strip() == r["label"])
    per = collections.defaultdict(lambda: [0, 0]); conf = collections.Counter()
    for r in recs:
        per[r["label"]][1] += 1; per[r["label"]][0] += r["correct"]
        conf[(r["label"], r["pred"] or "(판독불가)")] += 1
    lines = [f"# 평가 결과: {tag}", "", f"- 엔드포인트: `{url}`", f"- 문항 수: {n}",
             f"- **정확도: {correct}/{n} = {correct/n*100:.1f}%**",
             f"- 형식 준수(분야 이름만 정확히 출력): {exact}/{n} = {exact/n*100:.1f}%",
             f"- 판독 가능(응답에서 분야를 찾을 수 있음): {fmt_ok}/{n} = {fmt_ok/n*100:.1f}%", "",
             "## 분야별 정확도", "", "| 분야 | 정답/문항 | 정확도 |", "|---|---|---|"]
    for lab in labels:
        c, t = per[lab]; lines.append(f"| {lab} | {c}/{t} | {c/t*100:.0f}% |" if t else f"| {lab} | 0/0 | - |")
    lines += ["", "## 자주 틀린 조합 (정답 → 예측)", ""]
    for (a, p), k in sorted(conf.items(), key=lambda kv: -kv[1]):
        if a != p: lines.append(f"- {a} → {p}: {k}건")
    lines += ["", "## 틀린 예시 (앞 10개)", ""]
    for r in [r for r in recs if not r["correct"]][:10]:
        lines.append(f"- 「{r['text'][:60]}」 정답 {r['label']} / 응답 {r['raw'][:40]!r}")
    md = "\n".join(lines) + "\n"
    (HERE / "results" / f"{tag}_summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)


def compare(tags):
    rows = {}
    labels = None
    for tag in tags:
        p = HERE / "results" / f"{tag}.jsonl"
        recs = [json.loads(l) for l in open(p, encoding="utf-8")]
        labels = labels or list(dict.fromkeys(r["label"] for r in recs))
        per = collections.defaultdict(lambda: [0, 0])
        for r in recs:
            per[r["label"]][1] += 1; per[r["label"]][0] += r["correct"]
        rows[tag] = {"n": len(recs), "acc": sum(r["correct"] for r in recs) / len(recs),
                     "exact": sum(r["raw"].strip() == r["label"] for r in recs) / len(recs), "per": per}
    lines = ["# 튜닝 전후 비교", "", "| 항목 | " + " | ".join(tags) + " |", "|---|" + "---|" * len(tags)]
    lines.append("| 문항 수 | " + " | ".join(str(rows[t]["n"]) for t in tags) + " |")
    lines.append("| **정확도** | " + " | ".join(f"**{rows[t]['acc']*100:.1f}%**" for t in tags) + " |")
    lines.append("| 형식 준수 | " + " | ".join(f"{rows[t]['exact']*100:.1f}%" for t in tags) + " |")
    for lab in labels:
        lines.append(f"| {lab} | " + " | ".join(
            f"{rows[t]['per'][lab][0]/rows[t]['per'][lab][1]*100:.0f}%" if rows[t]['per'][lab][1] else "-" for t in tags) + " |")
    md = "\n".join(lines) + "\n"
    (HERE / "results" / "compare.md").write_text(md, encoding="utf-8")
    print(md)


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="HCX-003")
    ap.add_argument("--task", help="튜닝 작업 ID (주면 튜닝 모델로 평가)")
    ap.add_argument("--tag", help="결과 이름 (base, tuned, fewshot5 ...)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--fewshot", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.3, help="호출 간격(초). 429 나면 늘리기")
    ap.add_argument("--restart", action="store_true", help="이전 결과 무시하고 처음부터")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--compare", nargs="+", help="비교할 tag 들")
    args = ap.parse_args()
    if args.compare:
        compare(args.compare); return
    if not args.tag:
        args.tag = f"task_{args.task}" if args.task else args.model
    evaluate(args)


if __name__ == "__main__":
    main()
