import re
import numpy as np
import pandas as pd

detail = pd.read_csv("golfzon_detail.csv")
holes = pd.read_csv("golfzon_holes.csv")

# 1) 숨은 결측을 NaN으로
PLACEHOLDER = {"-", "_", ".", ""}
for c in ["상세_tel", "상세_fax", "상세_homepageUrl", "상세_address"]:
    s = detail[c].astype("string").str.strip()
    detail[c] = s.mask(s.isin(PLACEHOLDER))
holes["ladySeniorTee"] = holes["ladySeniorTee"].replace(0, np.nan)
holes["heightLadySeniorTee"] = holes["heightLadySeniorTee"].where(holes["ladySeniorTee"].notna())

# 2) Y/N 플래그 → 불리언 (상세에서 미지원은 빈 값으로 옴 → N)
FLAGS = ["상세_isVisionPlus", "상세_isNgs", "상세_isTvnx", "상세_isNxp",
         "상세_realityYn", "상세_membership", "상세_createdAt"]
failed = detail["상세_holeCount"].isna()            # 상세 수집 실패 행
for c in FLAGS:
    detail[c] = detail[c].fillna("N").eq("Y").astype("boolean")
    detail.loc[failed, c] = pd.NA

# 3) 값이 없거나 하나뿐인 컬럼, 중복 컬럼 삭제
drop = [c for c in detail.columns if detail[c].nunique(dropna=True) <= 1 and c not in FLAGS]
drop += ["상세_ciCode", "상세_ccName", "상세_areaName"]          # 코스ID·골프장명·지역과 중복
detail = detail.drop(columns=drop)
holes = holes.drop(columns=[c for c in holes.columns if holes[c].isna().all()])

# 4) 골프장명 공백 정리 + 골프장/코스조합 분리
detail["골프장명"] = detail["골프장명"].str.strip().str.replace(r"\s+", " ", regex=True)
holes["골프장명"] = holes["골프장명"].str.strip().str.replace(r"\s+", " ", regex=True)
parts = detail["골프장명"].str.split(" - ", n=1, expand=True)
detail["골프장"], detail["코스조합"] = parts[0].str.strip(), parts[1].str.strip()

# 5) 지역 구분 + 가상CC 주소·URL 정리
DOMESTIC = ["수도권", "경상도", "충청도", "전라도", "강원도", "제주도"]
detail["구분"] = np.select(
    [detail["지역"].isin(DOMESTIC), detail["지역"].eq("가상CC")], ["국내", "가상"], "해외")
desc_addr = (detail["상세_address"].str.contains(r"골프존|가상|코스|대회", na=False) & detail["구분"].ne("해외")) \
    | detail["상세_address"].str.match(r"^https?://", na=False)
detail.loc[desc_addr, "상세_address"] = pd.NA

# 6) 시도명 표준화 (국내 주소만)
SIDO = {"경기": "경기도", "경북": "경상북도", "경남": "경상남도", "전남": "전라남도", "전북": "전북특별자치도",
        "전라북도": "전북특별자치도", "충북": "충청북도", "충남": "충청남도", "강원": "강원특별자치도",
        "강원도": "강원특별자치도", "제주": "제주특별자치도", "제주도": "제주특별자치도", "서울": "서울특별시",
        "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시", "광주": "광주광역시",
        "울산": "울산광역시", "세종": "세종특별자치시",
        "제주시": "제주특별자치도", "횡성군": "강원특별자치도"}            # 시도 없이 시·군부터 쓴 주소
first = detail["상세_address"].str.split().str[0]
sido = first.replace(SIDO)
valid = sido.str.match(r".+(도|특별자치도|특별시|광역시|특별자치시)$", na=False) & detail["구분"].eq("국내")
detail["시도"] = sido.where(valid)
detail["지번주소"] = detail["상세_address"].str.contains(r"번지|\d+리\s|리 산", na=False)

# 7) 전화·팩스·URL 정규화
def norm_phone(s):
    if pd.isna(s):
        return pd.NA
    s = re.sub(r"\(0\)", "", str(s))
    return re.sub(r"[^\d+]", "", s) or pd.NA
detail["전화_정규화"] = detail["상세_tel"].map(norm_phone)
detail["팩스_정규화"] = detail["상세_fax"].map(norm_phone)

url = detail["상세_homepageUrl"].str.strip().str.replace(r"^htttp://", "http://", regex=True)
url = url.where(url.str.match(r"^https?://", na=True), "https://" + url)
url = url.mask(url.str.contains(r"golfzon\.com/?$", na=False) | ~url.str.contains(r"\.", na=True))
detail["상세_homepageUrl"] = url

# 8) 홀 테이블: 지역 붙이기, 홀번호, 티 순서 역전 플래그, 줄바꿈 제거

holes = holes.merge(detail[["코스ID", "지역", "구분"]], on="코스ID", how="left")
holes["홀번호"] = (holes["서브코스"] - 1) * 9 + holes["holeNo"]
holes["티순서역전"] = ((holes["frontTee"] > holes["backTee"]) | (holes["champTee"] > holes["backTee"])
                    | (holes["seniorTee"] > holes["frontTee"]) | (holes["ladyTee"] > holes["frontTee"]))
holes["description"] = holes["description"].str.replace(r"\r?\n", " ", regex=True).str.strip()
holes = holes.rename(columns={"frontTee": "whiteTee_front", "ladyTee": "redTee_lady"})

detail.to_csv("golfzon_courses_clean.csv", index=False, encoding="utf-8-sig")
holes.to_csv("golfzon_holes_clean.csv", index=False, encoding="utf-8-sig")
print("courses", detail.shape, "holes", holes.shape)
