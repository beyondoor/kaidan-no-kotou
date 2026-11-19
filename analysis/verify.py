"""画面（index.html）と同じ式で、板橋区の推定人数をもう一度計算する。

ブラウザの数字が正しいかを確かめるのと、町丁目ランキングの安定度を
画面より多い回数（既定 1000 回）で調べるためのスクリプト。

    python3 analysis/verify.py                  # 3つの場面の合計と上位10町丁目
    python3 analysis/verify.py --trials 1000    # 順位の安定度も出す
    python3 analysis/verify.py --csv out.csv    # 町丁目ごとの値をCSVに書く

使うのは標準ライブラリだけ。data.json.gz（または data.json）を読む。
"""
import argparse
import csv
import gzip
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 画面と同じ仮定（index.html の A と同じ値）
P6 = 0.05          # 6階建て以上でエレベーターがない確率
FH_DEFAULT = 3.0   # 階高が 2.5〜4.5m の外のときに使う値
FLOOD_MIN = 0.5    # これ未満の浸水深は数えない（床上浸水相当の線）
H_DEFAULT = 0.23   # 町丁目の65歳以上の割合が分からないときの値

SCENES = {"normal": "平時", "outage": "停電", "flood": "洪水＋停電"}


def load_data():
    gz = ROOT / "data.json.gz"
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(ROOT / "data.json", encoding="utf-8") as f:
        return json.load(f)


def floor_height(F, H):
    fh = H / F
    return fh if 2.5 <= fh <= 4.5 else FH_DEFAULT


def counted_floors(scene, F, fh, depth, T):
    """数える階の数と、エレベーターがない確率 p を返す。"""
    if scene == "flood":
        if (depth or 0) < FLOOD_MIN:
            return 0, 1.0
        k = min(F, math.ceil(depth / fh))          # 水につかる階
        return max(F - max(k, T - 1), 0), 1.0
    upper = max(F - (T - 1), 0)
    if scene == "normal":
        return upper, None                          # p はあとで決める
    return upper, 1.0


def estimate(data, scene, T=3, P=0.6):
    apt, chome = data["apt"], data["chome"]
    share65 = [c["a65"] / c["pop"] if c.get("pop") else None for c in chome]
    rows = []
    for i, F in enumerate(apt["F"]):
        fh = floor_height(F, apt["H"][i])
        upper, p = counted_floors(scene, F, fh, apt["fl"][i], T)
        if upper == 0:
            continue
        if p is None:
            p = P if F <= 5 else P6
        c = apt["ch"][i]
        h = share65[c] if c >= 0 and share65[c] is not None else H_DEFAULT
        lo = apt["R"][i] / F * upper * h * p
        hi = apt["Rhi"][i] / F * upper * h * p
        rows.append((i, c, lo, hi, p))
    return rows


def summarize(data, rows):
    chome = data["chome"]
    by = {}
    for _, c, lo, hi, _ in rows:
        if c < 0:
            continue
        q = by.setdefault(c, [0.0, 0.0, 0])
        q[0] += lo
        q[1] += hi
        q[2] += 1
    total_lo = sum(r[2] for r in rows)
    total_hi = sum(r[3] for r in rows)
    ranking = sorted(by.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
    return total_lo, total_hi, [(chome[c]["name"], (lo + hi) / 2, n) for c, (lo, hi, n) in ranking]


def stability(data, T=3, trials=1000, seed=1, top=10, keep=0.99):
    """建物ごとに p を 30〜90% でばらつかせて計算し直し、上位に残る割合を数える。"""
    rng = random.Random(seed)
    rows = estimate(data, "outage", T=T)   # 数える階は平時と同じで p=1。p はあとで掛ける
    F = data["apt"]["F"]
    n_ch = len(data["chome"])
    hit = [0] * n_ch
    for _ in range(trials):
        s = [0.0] * n_ch
        for i, c, lo, hi, _ in rows:
            if c < 0:
                continue
            p = 0.3 + 0.6 * rng.random() if F[i] <= 5 else P6
            s[c] += (lo + hi) / 2 * p
        for j in sorted(range(n_ch), key=lambda j: -s[j])[:top]:
            hit[j] += 1
    names = [c["name"] for c in data["chome"]]
    res = sorted(((names[j], hit[j] / trials) for j in range(n_ch) if hit[j]), key=lambda x: -x[1])
    return [(name, rate, rate >= keep) for name, rate in res]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--T", type=int, default=3, help="何階から上を数えるか（既定 3）")
    ap.add_argument("--P", type=float, default=0.6, help="平時のエレベーターがない確率（既定 0.6）")
    ap.add_argument("--trials", type=int, default=0, help="順位の安定度を調べる回数（0 なら調べない）")
    ap.add_argument("--csv", help="町丁目ごとの推定を書き出すCSVのパス")
    a = ap.parse_args()

    data = load_data()
    print(f"共同住宅 {len(data['apt']['F']):,} 棟／{a.T}階以上を数える")
    out = []
    for scene, label in SCENES.items():
        rows = estimate(data, scene, T=a.T, P=a.P)
        lo, hi, ranking = summarize(data, rows)
        print(f"\n[{label}] 約{(lo + hi) / 2:,.0f}人（{lo:,.0f}〜{hi:,.0f}人）／対象 {len(rows):,} 棟")
        for k, (name, mid, n) in enumerate(ranking[:10], 1):
            print(f"  {k:>2}. {name:<10} {mid:>7,.0f}人  {n:>4}棟")
        out += [(label, k, name, round(mid), n) for k, (name, mid, n) in enumerate(ranking, 1)]

    if a.trials:
        print(f"\n[平時・順位の安定度] {a.trials} 回、上位10に残った割合")
        for name, rate, ok in stability(data, T=a.T, trials=a.trials)[:15]:
            print(f"  {name:<10} {rate * 100:5.1f}%{'  順位が安定' if ok else ''}")

    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["場面", "順位", "町丁目", "推定人数（65歳以上）", "棟数"])
            w.writerows(out)
        print(f"\nCSV：{a.csv}")


if __name__ == "__main__":
    main()
