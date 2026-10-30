"""
골프존 코스 난이도 회귀분석
질문: 실제 스코어로 본 코스 난이도는 무엇으로 설명되는가?

입력 (같은 폴더): golfzon_grade.csv, golfzon_detail.csv, golfzon_holes.csv
출력: difficulty_index.csv, regression_summary.txt, images/*.png
필요 패키지: pip install statsmodels scikit-learn matplotlib
"""
import os
import warnings

import matplotlib
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import cross_val_score
from statsmodels.stats.outliers_influence import variance_inflation_factor

matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
plt.rcParams["font.family"] = ["AppleGothic", "Malgun Gothic", "NanumGothic", "Noto Sans CJK JP", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

MIN_ROUNDS = 30      # 이보다 라운드가 적은 등급 평균은 제외 (표본이 작아 불안정)
MIN_GRADES = 3       # 유효 등급이 이보다 적은 코스는 제외
LONG_PAR3 = 180      # 이 거리(m) 이상 Par 3를 '긴 Par 3'로 셈
os.makedirs("images", exist_ok=True)

# ───────────── 1. 목표변수: 난이도 지수 (실제 스코어 기준) ─────────────
grade = pd.read_csv("golfzon_grade.csv")
detail = pd.read_csv("golfzon_detail.csv")
holes = pd.read_csv("golfzon_holes.csv")

g = grade.merge(detail[["코스ID", "총파"]], on="코스ID")
g = g[g["라운드수"] >= MIN_ROUNDS].copy()
g["오버파"] = g["정밀평균타수"] - g["총파"]                       # 파 72·71 차이 보정
g["편차"] = g["오버파"] - g.groupby("등급")["오버파"].transform("mean")  # 같은 등급 평균 대비 몇 타 더 치나

idx = (g.groupby("코스ID")
         .apply(lambda d: pd.Series({"난이도지수": np.average(d["편차"], weights=d["라운드수"]),
                                     "유효등급수": len(d), "라운드합": d["라운드수"].sum()}))
         .reset_index())
idx = idx[idx["유효등급수"] >= MIN_GRADES]

# ───────────── 2. 설명변수: 코스 특성 ─────────────
DOMESTIC = ["수도권", "경상도", "충청도", "전라도", "강원도", "제주도"]
h = holes.copy()
feat_h = h.groupby("코스ID").apply(lambda d: pd.Series({
    "평균고저차_m": d["heightBackTee"].abs().mean(),
    "긴Par3수": ((d["basicPar"] == 3) & (d["backTee"] >= LONG_PAR3)).sum(),
    "Par4평균거리_m": d.loc[d["basicPar"] == 4, "backTee"].mean(),
})).reset_index()

c = detail[["코스ID", "골프장명", "지역", "홀수", "총파", "총거리",
            "상세_difficultyCc", "상세_difficultyGreen"]].copy()
c = c[(c["홀수"] == 18) & (c["총파"] >= 70)]                    # 18홀 정규 코스만
c["총거리_km"] = c["총거리"] / 1000
c["가상CC"] = c["지역"].eq("가상CC").astype(int)
c["해외"] = (~c["지역"].isin(DOMESTIC + ["가상CC"])).astype(int)
c = c.rename(columns={"상세_difficultyCc": "공식난이도_코스", "상세_difficultyGreen": "공식난이도_그린"})

df = idx.merge(c, on="코스ID").merge(feat_h, on="코스ID").dropna()
print(f"분석 대상: {len(df)}개 코스 (라운드 {MIN_ROUNDS}회 이상 등급 {MIN_GRADES}개 이상)")

PHYS = ["총거리_km", "평균고저차_m", "긴Par3수", "Par4평균거리_m", "가상CC", "해외"]
OFFICIAL = ["공식난이도_코스", "공식난이도_그린"]


# ───────────── 3. OLS 회귀 (표준화 계수, 강건 표준오차) ─────────────
def ols(cols):
    X = df[cols].astype(float)
    Xz = (X - X.mean()) / X.std()
    return sm.OLS(df["난이도지수"], sm.add_constant(Xz)).fit(cov_type="HC3")


mA, mB = ols(PHYS), ols(PHYS + OFFICIAL)
Xv = df[PHYS + OFFICIAL].astype(float)
vif = pd.Series([variance_inflation_factor(sm.add_constant(Xv).values, i + 1) for i in range(Xv.shape[1])],
                index=Xv.columns).round(2)

# ───────────── 4. 비선형 확인: 랜덤포레스트 ─────────────
rf = RandomForestRegressor(n_estimators=400, min_samples_leaf=5, random_state=0)
cv_r2 = cross_val_score(rf, df[PHYS + OFFICIAL], df["난이도지수"], cv=5, scoring="r2")
rf.fit(df[PHYS + OFFICIAL], df["난이도지수"])
pi = permutation_importance(rf, df[PHYS + OFFICIAL], df["난이도지수"], n_repeats=20, random_state=0)
imp = pd.Series(pi.importances_mean, index=PHYS + OFFICIAL).sort_values(ascending=False)

# ───────────── 5. 결과 저장 ─────────────
with open("regression_summary.txt", "w", encoding="utf-8") as f:
    f.write(f"분석 대상 {len(df)}개 코스 / 난이도지수 평균 {df['난이도지수'].mean():.2f}, "
            f"표준편차 {df['난이도지수'].std():.2f}타\n\n")
    f.write("[모델 A] 물리적 특성만\n" + mA.summary().as_text() + "\n\n")
    f.write("[모델 B] + 골프존 공식 난이도\n" + mB.summary().as_text() + "\n\n")
    f.write(f"VIF\n{vif.to_string()}\n\n")
    f.write(f"랜덤포레스트 5-fold CV R²: {cv_r2.mean():.3f} (±{cv_r2.std():.3f})\n")
    f.write(f"순열 중요도\n{imp.round(4).to_string()}\n")

out = df.sort_values("난이도지수", ascending=False)
out.to_csv("difficulty_index.csv", index=False, encoding="utf-8-sig")

print(f"\n모델 A (물리적 특성)   R² = {mA.rsquared:.3f}, 조정 R² = {mA.rsquared_adj:.3f}")
print(f"모델 B (+ 공식 난이도) R² = {mB.rsquared:.3f}, 조정 R² = {mB.rsquared_adj:.3f}")
print(f"랜덤포레스트 CV R²     = {cv_r2.mean():.3f}")
print("\n[모델 B 표준화 계수] (1 표준편차 늘 때 난이도지수 변화, 타)")
print(pd.DataFrame({"계수": mB.params, "p값": mB.pvalues}).drop("const").round(3).to_string())
print("\n가장 어려운 코스 Top 5:\n", out[["골프장명", "지역", "난이도지수"]].head(5).round(2).to_string(index=False))
print("\n가장 쉬운 코스 Top 5:\n", out[["골프장명", "지역", "난이도지수"]].tail(5).round(2).to_string(index=False))

# ───────────── 6. 차트 ─────────────
coef = mB.params.drop("const")
ci = mB.conf_int().drop("const")
order = coef.sort_values().index
fig, ax = plt.subplots(figsize=(8, 4.5))
colors = ["#C0392B" if mB.pvalues[k] < 0.05 else "#999999" for k in order]
ax.errorbar(coef[order], range(len(order)), xerr=[coef[order] - ci.loc[order, 0], ci.loc[order, 1] - coef[order]],
            fmt="none", ecolor="#BBBBBB", capsize=3)
ax.scatter(coef[order], range(len(order)), color=colors, zorder=3, s=40)
ax.axvline(0, color="#666", lw=0.8)
ax.set_yticks(range(len(order)), order)
ax.set_xlabel("표준화 계수 (타, 95% 신뢰구간)")
ax.set_title(f"무엇이 실제 스코어를 높이나 (빨강 = p<0.05, R²={mB.rsquared:.2f})", loc="left", fontweight="bold")
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("images/01_coefficients.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(6, 5.5))
ax.scatter(mB.fittedvalues, df["난이도지수"], s=14, alpha=0.6, color="#2F6FB0")
lim = [df["난이도지수"].min() - 0.5, df["난이도지수"].max() + 0.5]
ax.plot(lim, lim, color="#C0392B", lw=1, ls="--")
ax.set_xlabel("예측 난이도지수 (타)"); ax.set_ylabel("실제 난이도지수 (타)")
ax.set_title("예측 vs 실제 (모델 B)", loc="left", fontweight="bold")
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("images/02_pred_vs_actual.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 5))
jit = np.random.default_rng(0).uniform(-0.15, 0.15, len(df))
ax.scatter(df["공식난이도_코스"] + jit, df["난이도지수"], s=14, alpha=0.6, color="#2F6FB0")
m = df.groupby("공식난이도_코스")["난이도지수"].mean()
ax.plot(m.index, m.values, color="#C0392B", marker="o", lw=2, label="난이도별 평균")
ax.set_xlabel("골프존 공식 코스 난이도"); ax.set_ylabel("실제 난이도지수 (타)")
ax.set_title("공식 난이도는 실제 스코어와 맞을까", loc="left", fontweight="bold")
ax.legend(frameon=False)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("images/03_official_vs_actual.png", dpi=150); plt.close(fig)
print("\n저장: difficulty_index.csv, regression_summary.txt, images/01~03")
