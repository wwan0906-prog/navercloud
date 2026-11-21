"""민원 가이드 DB (SQLite)

- 가이드 데이터(18개 대분류 · 분야별 필수 정보 · 공식 접수 채널)는 data/guide_seed.json 이 원본입니다.
  init() 이 서버 시작 때마다 JSON → SQLite 로 다시 적재합니다.
- 분석 기록(complaints)은 재시작해도 유지됩니다.

경로는 환경변수 DB_PATH / GUIDE_SEED_PATH 로 바꿀 수 있습니다 (테스트용).
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
KST = timezone(timedelta(hours=9))

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id          TEXT PRIMARY KEY,      -- 대분류 라벨 (AI Hub 18개)
    name        TEXT NOT NULL,         -- 화면 표시 이름
    description TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fields (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id TEXT NOT NULL REFERENCES categories(id),
    key         TEXT NOT NULL,
    label       TEXT NOT NULL,
    required    INTEGER NOT NULL DEFAULT 1,
    when_rule   TEXT,                  -- 조건부 필수 조건 (seed 의 when). NULL 이면 항상 필수
    check_rule  TEXT,                  -- 충족 판정 기준 문장 (seed 의 check)
    min_length  INTEGER,
    pattern     TEXT,
    hint        TEXT,
    example     TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (category_id, key)
);
-- category_id 가 NULL 이면 기본(공통) 접수 채널
CREATE TABLE IF NOT EXISTS channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id TEXT UNIQUE REFERENCES categories(id),
    agency      TEXT NOT NULL,
    url         TEXT,
    phone       TEXT
);
CREATE TABLE IF NOT EXISTS complaints (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    complaint_text TEXT NOT NULL,     -- 사용자가 입력한 텍스트 + OCR 텍스트를 합친 분석 대상
    image_count   INTEGER NOT NULL DEFAULT 0,
    main_category TEXT,
    is_complete   INTEGER,
    result_json   TEXT NOT NULL
);
"""
GUIDE_TABLES = ('channels', 'fields', 'categories')


def db_path() -> Path:
    return Path(os.environ.get('DB_PATH') or DATA_DIR / 'minwon.db')


def seed_path() -> Path:
    return Path(os.environ.get('GUIDE_SEED_PATH') or DATA_DIR / 'guide_seed.json')


@contextmanager
def connect():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- 초기화 / 적재
def init() -> dict:
    """테이블을 만들고 가이드 데이터를 JSON 에서 다시 적재합니다. 적재 개수를 돌려줍니다."""
    db_path().parent.mkdir(parents=True, exist_ok=True)
    seed = json.loads(seed_path().read_text(encoding='utf-8'))
    counts = {'categories': 0, 'fields': 0, 'channels': 0}
    with connect() as conn:
        # 예전 구조(세부 유형 있던 버전)의 가이드 테이블이 남아 있으면 지우고 새로 만듦
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'subtypes'").fetchone():
            conn.executescript('DROP TABLE IF EXISTS channels; DROP TABLE IF EXISTS fields;'
                               ' DROP TABLE IF EXISTS subtypes; DROP TABLE IF EXISTS categories;'
                               ' DROP TABLE IF EXISTS complaints;')
        # 가이드 테이블은 매번 새로 만듦 (컬럼이 바뀌어도 예전 DB 파일을 지울 필요 없게)
        for table in GUIDE_TABLES:
            conn.execute(f'DROP TABLE IF EXISTS {table}')
        conn.executescript(SCHEMA)

        def add_channel(ch, category_id=None):
            if ch:
                conn.execute('INSERT INTO channels (category_id, agency, url, phone) VALUES (?, ?, ?, ?)',
                             (category_id, ch['agency'], ch.get('url'), ch.get('phone')))
                counts['channels'] += 1

        add_channel(seed.get('default_channel'))
        for i, cat in enumerate(seed.get('categories', [])):
            conn.execute('INSERT INTO categories (id, name, description, sort_order) VALUES (?, ?, ?, ?)',
                         (cat['id'], cat.get('name', cat['id']), cat.get('description'), i))
            counts['categories'] += 1
            add_channel(cat.get('official_channel'), category_id=cat['id'])
            for j, f in enumerate(cat.get('fields', [])):
                conn.execute(
                    'INSERT INTO fields (category_id, key, label, required, when_rule, check_rule,'
                    ' min_length, pattern, hint, example, sort_order)'
                    ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (cat['id'], f['key'], f.get('label', f['key']), int(f.get('required', True)),
                     f.get('when'), f.get('check'), f.get('min_length'), f.get('pattern'),
                     f.get('hint'), f.get('example'), j))
                counts['fields'] += 1
    return counts


# ---------------------------------------------------------------- 가이드 조회
def _channel(conn, category_id: str | None) -> dict | None:
    if category_id is None:
        row = conn.execute('SELECT agency, url, phone FROM channels WHERE category_id IS NULL').fetchone()
    else:
        row = conn.execute('SELECT agency, url, phone FROM channels WHERE category_id = ?',
                           (category_id,)).fetchone()
    return dict(row) if row else None


def default_channel() -> dict | None:
    with connect() as conn:
        return _channel(conn, None)


def get_category(category_id: str) -> dict | None:
    """대분류 하나를 필수 정보 항목·접수 채널까지 묶어서 돌려줍니다. 없으면 None.
    official_channel 은 분야 전용 채널이 없으면 None (기본 채널은 default_channel())."""
    with connect() as conn:
        row = conn.execute('SELECT id, name, description FROM categories WHERE id = ?',
                           (category_id,)).fetchone()
        if row is None:
            return None
        category = dict(row)
        category['fields'] = [
            {**dict(f), 'required': bool(f['required'])}
            for f in conn.execute(
                'SELECT key, label, required, when_rule AS "when", check_rule AS "check",'
                ' min_length, pattern, hint, example FROM fields WHERE category_id = ? ORDER BY sort_order', (category_id,))
        ]
        category['official_channel'] = _channel(conn, category_id)
        return category


def list_categories() -> list[dict]:
    with connect() as conn:
        ids = [r['id'] for r in conn.execute('SELECT id FROM categories ORDER BY sort_order')]
    return [get_category(i) for i in ids]


# ---------------------------------------------------------------- 분석 기록
def save_complaint(complaint_text: str, image_count: int, result: dict) -> tuple[int, str]:
    created_at = datetime.now(KST).isoformat(timespec='seconds')
    with connect() as conn:
        cur = conn.execute(
            'INSERT INTO complaints (created_at, complaint_text, image_count, main_category,'
            ' is_complete, result_json) VALUES (?, ?, ?, ?, ?, ?)',
            (created_at, complaint_text, image_count, result.get('main_category'),
             int(bool(result.get('is_complete'))), json.dumps(result, ensure_ascii=False)))
        return cur.lastrowid, created_at


def get_complaint(complaint_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute('SELECT * FROM complaints WHERE id = ?', (complaint_id,)).fetchone()
    if row is None:
        return None
    result = json.loads(row['result_json'])
    result.update(id=row['id'], created_at=row['created_at'])
    return result


def list_complaints(limit: int = 20) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            'SELECT id, created_at, main_category, image_count, is_complete,'
            ' substr(complaint_text, 1, 60) AS preview FROM complaints ORDER BY id DESC LIMIT ?',
            (limit,))
        return [{**dict(r), 'is_complete': bool(r['is_complete'])} for r in rows]
