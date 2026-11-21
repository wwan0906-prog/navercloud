"""AI허브 619 「민원 업무 자동화 인공지능 언어 데이터」 → HCX 튜닝용 데이터셋 변환

사용법:
    python prepare_data.py --root <TL1 압축 푼 폴더> [--cap 400] [--test-per-cat 50] [--mapping mapping.json]

입력:  TL1(Training 라벨링데이터) 폴더. 분야별 json 18개 (파일명 '#Uxxxx'로 깨져 있어도 됨)
출력 (--out 폴더, 기본 ./dataset):
    train.csv              CLOVA Studio 튜닝 형식 (System_Prompt, C_ID, T_ID, Text, Completion), UTF-8 BOM
    test.jsonl             튜닝 전/후 공통 평가셋  {id, text, label, orig_category, subcategory, source}
    fewshot_subcategory.json  분야별 하위분류 예문 (세부 유형 프롬프트 few-shot용)
    fewshot_entities.json     LOC/DAT/TIM/QTT 개체명 예문 (정보 추출 프롬프트 few-shot용)
    department_map.json       분야·하위분류별 담당 부서 상위 목록 (가이드 DB 초안용, 창원시 기준)
    stats.md                  분야별 건수 (발표 "사용 데이터셋과 데이터 수" 항목에 그대로 사용)

중요:
  * VL1(Validation)은 TL1 원문의 유사 문장이라(기준 ID 100% 겹침) 평가셋으로 쓰면 안 됨.
    → 여기서는 TL1만 쓰고, 기준 ID(B12345 / C678) 단위로 train/test를 나눠 누수를 막는다.
  * 한 기준 ID에는 원문(-0)과 유사 문장(-1~-4)이 있음. 대표 1건(원문 우선)만 사용.
  * 자동차 쏠림(원문 기준 30%)을 막기 위해 분야별 상한(--cap)으로 균등 샘플링.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import random
import re
from pathlib import Path

SYSTEM_PROMPT = (
    "당신은 지방자치단체 민원 분류 담당자입니다. 민원 내용을 읽고 아래 8개 분야 중 하나로만 답하세요.\n"
    "분야: {labels}\n"
    "답은 분야 이름만 출력합니다."
)

# 18개 원본 대분류 → 8개 서비스 분야 (기본값. --mapping 으로 JSON 파일을 주면 그것을 씀)
DEFAULT_MAPPING = {
    "교통·자동차": ["자동차", "교통"],
    "도로·안전시설": ["안전건설"],
    "건축·토지": ["건축허가", "토지"],
    "환경·위생": ["환경미화", "위생", "상하수도"],
    "산림·농업": ["산림", "농업_축산"],
    "복지·보건": ["복지", "보건소"],
    "세무·행정": ["세무", "행정", "공통", "정보통신"],
    "경제·문화": ["경제", "문화_체육_관광"],
}

ENTITY_LABELS_FOR_EXTRACTION = {"LOC": "위치", "DAT": "날짜", "TIM": "시간", "QTT": "수량", "AFW": "물건/시설"}


def decode_name(s: str) -> str:
    """unzip이 '#Uc0b0#Ub9bc' 처럼 깨뜨린 한글 파일명을 복원"""
    return re.sub(r"#U([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def base_id(doc_id: str) -> str:
    return doc_id.split("-")[0]


def suffix(doc_id: str) -> int:
    return int(doc_id.split("-")[1]) if "-" in doc_id else -1


def stable_bucket(key: str, buckets: int = 100) -> int:
    """기준 ID를 안정적으로 0~99 버킷에 배정 (실행할 때마다 같은 분할)"""
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % buckets


def mask_pii(text: str) -> str:
    text = re.sub(r"\d{2,3}-\d{3,4}-\d{4}", "[전화번호]", text)
    text = re.sub(r"\d{6}-\d{7}", "[주민번호]", text)
    return text


def load_documents(root: Path):
    files = sorted(p for p in root.rglob("*.json"))
    if not files:
        raise SystemExit(f"json 파일이 없습니다: {root}")
    for f in files:
        print(f"  읽는 중: {decode_name(f.name)}")
        data = json.loads(f.read_text(encoding="utf-8"))
        docs = data["documents"] if isinstance(data, dict) else data
        for d in docs:
            yield d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="TL1 압축을 푼 폴더")
    ap.add_argument("--out", default="dataset")
    ap.add_argument("--cap", type=int, default=400, help="분야별 학습 데이터 상한")
    ap.add_argument("--test-per-cat", type=int, default=50, help="분야별 테스트 건수")
    ap.add_argument("--test-ratio", type=int, default=10, help="테스트로 떼어둘 기준 ID 비율(%)")
    ap.add_argument("--mapping", help="18→8 매핑 JSON 파일 (없으면 기본값)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-len", type=int, default=10, help="이보다 짧은 문장은 제외")
    args = ap.parse_args()

    random.seed(args.seed)
    mapping = json.loads(Path(args.mapping).read_text(encoding="utf-8")) if args.mapping else DEFAULT_MAPPING
    to_label = {orig: lab for lab, origs in mapping.items() for orig in origs}
    labels = list(mapping.keys())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # 1) 기준 ID별 대표 문서 1건 (원문 -0 우선)
    print("[1/4] 문서 읽기")
    rep: dict[str, dict] = {}
    unmapped = collections.Counter()
    sub_examples = collections.defaultdict(lambda: collections.defaultdict(list))
    ent_examples = collections.defaultdict(list)
    dept_counter = collections.defaultdict(collections.Counter)
    for d in load_documents(Path(args.root)):
        cat = d["labeling"]["intent"]["category"]
        if cat not in to_label:
            unmapped[cat] += 1
            continue
        b = base_id(d["id"])
        if b not in rep or suffix(d["id"]) < suffix(rep[b]["id"]):
            rep[b] = d
    if unmapped:
        print(f"  매핑에 없는 분야(제외됨): {dict(unmapped)}")

    # 2) 통계·few-shot·부서 수집 (대표 문서 기준)
    print("[2/4] 집계")
    for d in rep.values():
        lab = d["labeling"]
        cat = lab["intent"]["category"]
        sub = lab["intent"]["subcategory"]
        text = d["Q_refined"].strip()
        dept_counter[(cat, sub)][lab.get("department") or ""] += 1
        if sub != "기타" and len(sub_examples[cat][sub]) < 3 and 15 <= len(text) <= 120:
            sub_examples[cat][sub].append(text)
        ents = [e for e in lab.get("entities", []) if e.get("label") in ENTITY_LABELS_FOR_EXTRACTION]
        if len(ents) >= 2 and len(ent_examples[cat]) < 5 and len(text) <= 150:
            ent_examples[cat].append({
                "text": text,
                "entities": [{"형태": e["form"], "유형": ENTITY_LABELS_FOR_EXTRACTION[e["label"]]} for e in ents],
            })

    # 3) 기준 ID 해시로 train/test 분할 → 분야별 샘플링
    print("[3/4] 분할·샘플링")
    pool_train = collections.defaultdict(list)
    pool_test = collections.defaultdict(list)
    for b, d in rep.items():
        text = mask_pii(d["Q_refined"].strip().replace("\n", " "))
        if len(text) < args.min_len:
            continue
        lab = to_label[d["labeling"]["intent"]["category"]]
        row = {
            "id": d["id"], "text": text, "label": lab,
            "orig_category": d["labeling"]["intent"]["category"],
            "subcategory": d["labeling"]["intent"]["subcategory"],
            "predication": d["labeling"]["intent"]["predication"],
            "source": "콜센터" if b.startswith("C") else "민원게시판",
        }
        (pool_test if stable_bucket(b) < args.test_ratio else pool_train)[lab].append(row)

    train, test = [], []
    for lab in labels:
        tr, te = pool_train[lab], pool_test[lab]
        random.shuffle(tr); random.shuffle(te)
        train += tr[: args.cap]
        test += te[: args.test_per_cat]
    random.shuffle(train)

    # 4) 저장
    print("[4/4] 저장")
    sys_prompt = SYSTEM_PROMPT.format(labels=", ".join(labels))
    with open(out / "train.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["System_Prompt", "C_ID", "T_ID", "Text", "Completion"])
        for i, r in enumerate(train):
            w.writerow([sys_prompt, i, 0, r["text"], r["label"]])
    with open(out / "test.jsonl", "w", encoding="utf-8") as f:
        for r in test:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "system_prompt.txt").write_text(sys_prompt, encoding="utf-8")
    (out / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "fewshot_subcategory.json").write_text(
        json.dumps({c: dict(s) for c, s in sub_examples.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "fewshot_entities.json").write_text(json.dumps(ent_examples, ensure_ascii=False, indent=2), encoding="utf-8")
    dept_map = {f"{c}/{s}": [d for d, _ in cnt.most_common(3) if d] for (c, s), cnt in dept_counter.items()}
    (out / "department_map.json").write_text(json.dumps(dept_map, ensure_ascii=False, indent=2), encoding="utf-8")

    # stats.md
    orig_cnt = collections.Counter(d["labeling"]["intent"]["category"] for d in rep.values())
    lines = ["# 데이터셋 통계", "",
             f"- 원본: AI허브 「민원 업무 자동화 인공지능 언어 데이터」(dataSetSn=619) Training 라벨링 데이터",
             f"- 기준 ID(원문) 수: {len(rep):,} / 학습에 쓴 문장: {len(train):,} / 평가 문장: {len(test):,}",
             f"- 분할: 기준 ID 해시 기준 test {args.test_ratio}% 분리 후 분야별 상한 {args.cap}, 평가 {args.test_per_cat}건 샘플링 (seed={args.seed})",
             "", "| 서비스 분야 | 원본 대분류(원문 건수) | 학습 | 평가 |", "|---|---|---|---|"]
    tr_cnt = collections.Counter(r["label"] for r in train)
    te_cnt = collections.Counter(r["label"] for r in test)
    for lab in labels:
        srcs = ", ".join(f"{o}({orig_cnt[o]:,})" for o in mapping[lab])
        lines.append(f"| {lab} | {srcs} | {tr_cnt[lab]} | {te_cnt[lab]} |")
    (out / "stats.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n완료: {out.resolve()}")


if __name__ == "__main__":
    main()
