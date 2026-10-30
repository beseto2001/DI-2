"""
골프존 등급별 평균 타수 수집 (grade/average API)
- 입력: golfzon_list.csv (코스ID 514개)
- 1단계: 첫 골프장 응답 구조를 출력 (PREVIEW_ONLY = True)
- 2단계: 전체 수집 → 원본 JSON 캐시 + CSV 저장 (PREVIEW_ONLY = False)

같은 폴더(web/GolfZone)에서 실행하세요.
"""
import json
import os
import time

import pandas as pd
import requests

# ───────────── 설정 ─────────────
INPUT_CSV = "golfzon_list.csv"
OUTPUT_CSV = "golfzon_grade.csv"            # 골프장 × 등급 1행
OUTPUT_WIDE_CSV = "golfzon_grade_wide.csv"  # 골프장 1행 (분석·추천용)
CACHE_DIR = "cache_grade"          # 골프장별 원본 JSON (재실행 시 재요청 안 함)
PREVIEW_ONLY = False               # True면 첫 골프장 응답만 출력

# 실력 높은 순 (독수리 → 참새). 목록에 없는 등급은 맨 뒤로
GRADE_ORDER = {"EA": 1, "FA": 2, "CR": 3, "MA": 4, "SP": 5}
LIMIT = None                       # 테스트용 개수 제한 (예: 5)
DELAY = 0.5                        # 요청 간격(초)

URL = "https://lobby.golfzon.com/v1/dotcom/courses/course/{ci}/grade/average"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.golfzon.com/",
    "Origin": "https://www.golfzon.com",
}


def fetch(ci):
    """골프장 1곳의 응답. 캐시가 있으면 파일에서 읽음"""
    path = os.path.join(CACHE_DIR, f"{ci}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f), False
    r = requests.get(URL.format(ci=ci), headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json() if r.text.strip() else None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data, True


def to_rows(ci, data):
    """응답 모양에 상관없이 행(dict) 목록으로 변환"""
    if data is None:
        return [{"코스ID": ci}]
    if isinstance(data, dict):
        # dict 안에 행 목록(list of dict)이 있으면 그걸 펼침
        lists = [v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if lists:
            base = {k: v for k, v in data.items() if not isinstance(v, (list, dict))}
            return [{"코스ID": ci, **base, **row} for row in pd.json_normalize(lists[0]).to_dict("records")]
        return [{"코스ID": ci, **pd.json_normalize(data).to_dict("records")[0]}]
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return [{"코스ID": ci, **row} for row in pd.json_normalize(data).to_dict("records")]
        return [{"코스ID": ci, "value": json.dumps(data, ensure_ascii=False)}]
    return [{"코스ID": ci, "value": data}]


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    courses = pd.read_csv(INPUT_CSV)
    if LIMIT:
        courses = courses.head(LIMIT)

    # 1단계: 구조 확인
    if PREVIEW_ONLY:
        ci = courses["코스ID"].iloc[0]
        data, _ = fetch(ci)
        print(f"[미리보기] 코스ID {ci} ({courses['골프장명'].iloc[0]}) 응답:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        print("\n구조가 괜찮으면 PREVIEW_ONLY = False 로 바꾸고 다시 실행하세요.")
        return

    # 2단계: 전체 수집
    rows, failed = [], []
    for i, (ci, name) in enumerate(zip(courses["코스ID"], courses["골프장명"]), 1):
        try:
            data, requested = fetch(ci)
        except Exception as e:
            failed.append(ci)
            print(f"  ⚠️ [{i}] {name} 실패: {type(e).__name__}")
            continue
        new = to_rows(ci, data)
        for r in new:
            r["골프장명"] = name
        rows += new
        if i % 50 == 0 or i == len(courses):
            print(f"[{i}/{len(courses)}] 진행 중… (누적 {len(rows)}행)")
        if requested:
            time.sleep(DELAY)

    # ── 정리: 골프장 × 등급 1행 (long)
    df = pd.DataFrame(rows).dropna(subset=["gradeCode"])
    df["정밀평균타수"] = (df["totalHit"] / df["totalRound"]).round(2)   # avgHit는 정수 반올림값
    df["집계시각"] = pd.to_datetime(df["createDate"], unit="s", utc=True).dt.tz_convert("Asia/Seoul")
    df["등급순서"] = df["gradeCode"].map(GRADE_ORDER).fillna(99).astype(int)
    df = df.rename(columns={"gradeCode": "등급코드", "gradeName": "등급", "avgHit": "평균타수",
                            "totalRound": "라운드수", "totalHit": "총타수"})
    long = df[["코스ID", "골프장명", "등급순서", "등급코드", "등급", "평균타수", "정밀평균타수",
               "라운드수", "총타수", "집계시각"]].sort_values(["코스ID", "등급순서"])
    long.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    # ── 분석용: 골프장 1행 (wide) — 등급별 평균 타수·라운드 수
    order = long.drop_duplicates("등급").sort_values("등급순서")["등급"].tolist()
    avg = long.pivot(index="코스ID", columns="등급", values="정밀평균타수")[order].add_prefix("평균_")
    cnt = long.pivot(index="코스ID", columns="등급", values="라운드수")[order].add_prefix("라운드_")
    wide = courses[["코스ID", "골프장명", "지역"]].merge(avg.join(cnt).reset_index(), on="코스ID", how="left")
    wide["총라운드"] = wide.filter(like="라운드_").sum(axis=1)
    wide.to_csv(OUTPUT_WIDE_CSV, index=False, encoding="utf-8-sig")

    print(f"\n완료 → {OUTPUT_CSV} ({len(long)}행), {OUTPUT_WIDE_CSV} ({len(wide)}행), 실패 {len(failed)}곳")
    print("등급별 행 수:", long["등급"].value_counts().reindex(order).to_dict())
    if failed:
        print("실패 코스ID:", failed)


if __name__ == "__main__":
    main()
