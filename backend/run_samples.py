"""samples.txt 의 민원을 전부 analyze() 에 넣고 결과를 표로 저장

    python3 run_samples.py                 # 전체 (60개 × 3회 호출, 약 6~7분)
    python3 run_samples.py --limit 10      # 앞 10개만
    python3 run_samples.py --from 20       # 20번째부터 (중간에 끊겼을 때)

결과: results/samples_결과.md (사람이 보는 표), results/samples_결과.jsonl (원본)
"""
import json
import sys
import time
from pathlib import Path

from analyze import analyze

HERE = Path(__file__).resolve().parent
lines = [l.strip() for l in (HERE / "samples.txt").read_text(encoding="utf-8").splitlines()]
samples = [l for l in lines if l and not l.startswith("#")]

limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else len(samples)
start = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 0
samples = samples[start:start + limit]

out_dir = HERE / "results"; out_dir.mkdir(exist_ok=True)
md = ["# 샘플 민원 분석 결과", "", "| # | 민원 | 분야 > 세부 | 누락 | 불충분 | 1순위 채널 | 초 |", "|---|---|---|---|---|---|---|"]
with open(out_dir / "samples_결과.jsonl", "a", encoding="utf-8") as jf:
    for i, text in enumerate(samples, start + 1):
        try:
            r = analyze(text)
        except Exception as e:
            print(f"[{i}] 오류: {e}"); time.sleep(3); continue
        jf.write(json.dumps(r, ensure_ascii=False) + "\n"); jf.flush()
        if "error" in r:
            print(f"[{i}] 판독 실패: {r}"); continue
        ch = r["channels"][0]["name"] if r["channels"] else ""
        print(f"[{i}] {r['category']} > {r['subtype']} | 누락 {len(r['missing'])} 불충분 {len(r['insufficient'])} | {text[:30]}")
        md.append(f"| {i} | {text[:40]} | {r['category']} > {r['subtype']} | {', '.join(r['missing'])} | "
                  f"{', '.join(r['insufficient'])} | {ch} | {r['_debug']['elapsed_sec']} |")
        time.sleep(0.3)

(out_dir / "samples_결과.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n저장:", out_dir / "samples_결과.md")
