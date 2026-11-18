"""PLATEAUから抜き出した板橋区の建物データと、町丁目別人口を結合して、デモ用の data.json を作る。
使い方: python3 prep.py itabashi_plateau_buildings.json itabashi_age_by_chome.csv out/data.json
"""
import json, sys, csv, math, re

src, census_csv, out = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(src, encoding="utf-8"))

KAN = {"一": "１", "二": "２", "三": "３", "四": "４", "五": "５", "六": "６", "七": "７", "八": "８", "九": "９"}

def norm(name):
    # 「高島平二丁目」→「高島平２丁目」
    m = re.match(r"^(.*?)([一二三四五六七八九])丁目$", name)
    if m:
        return m.group(1) + KAN[m.group(2)] + "丁目"
    return name

census = {}
with open(census_csv, encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("#") or row[0] == "name":
            continue
        name, pop, a65, a75, hh = row[:5]
        census[name] = dict(pop=int(pop), a65=int(a65), a75=int(a75), hh=int(hh) if hh else 0)

# 町丁目コード → 名前・人口
codes = sorted(d["names"].keys())
chome = []
code_idx = {}
miss = []
for c in codes:
    nm = norm(d["names"][c])
    cs = census.get(nm)
    if cs is None:
        miss.append(nm)
    code_idx[int(c[5:])] = len(chome)
    chome.append(dict(code=c, name=nm, **(cs or dict(pop=0, a65=0, a75=0, hh=0))))

def poly_area(xy):
    n = len(xy) // 2
    s = 0.0
    for i in range(n):
        x1, y1 = xy[2 * i], xy[2 * i + 1]
        x2, y2 = xy[2 * ((i + 1) % n)], xy[2 * ((i + 1) % n) + 1]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2

# 同じ建物が複数のタイルに入っていることがあるので、建物IDで重なりを除く（形の面積が大きい方を残す）
best = {}
for r in d["apts"]:
    k = r[0]
    if k not in best or poly_area(r[11]) > poly_area(best[k][11]):
        best[k] = r
print("apartments before/after dedupe:", len(d["apts"]), len(best))
apt = dict(id=[], ch=[], F=[], H=[], A=[], Asrc=[], fl=[], fl1=[], rv=[], dur=[], fp=[], off=[0], xy=[])
for r in best.values():
    bid, ch, F, below, H, roof, fp, fl2, fl1, rv, dur, xy = r
    if not F or F <= 0:
        continue
    area = roof if roof and roof > 0 else poly_area(xy)
    apt["id"].append(bid)
    apt["ch"].append(code_idx.get(ch, -1))
    apt["F"].append(int(F))
    apt["H"].append(H)
    apt["A"].append(round(area))
    apt["Asrc"].append(1 if roof and roof > 0 else 0)
    apt["fl"].append(fl2)
    apt["fl1"].append(fl1)
    apt["rv"].append(rv)
    apt["dur"].append(dur)
    apt["fp"].append(fp)
    apt["xy"].extend(xy)
    apt["off"].append(len(apt["xy"]))

ctx = dict(h=[], off=[0], xy=[])
seen = set()
for h, known, xy in d["ctx"]:
    if poly_area(xy) < 12:
        continue
    key = (round(xy[0]), round(xy[1]), round(h or 0))
    if key in seen:
        continue
    seen.add(key)
    ctx["h"].append(h if h and h > 0 else 3.0)
    ctx["xy"].extend(xy)
    ctx["off"].append(len(ctx["xy"]))

# 町丁目の重心（共同住宅と周辺建物の位置から）
sx = [0.0] * len(chome); sy = [0.0] * len(chome); sn = [0] * len(chome)
for i, c in enumerate(apt["ch"]):
    if c < 0:
        continue
    a, b = apt["off"][i], apt["off"][i + 1]
    xs = apt["xy"][a:b:2]; ys = apt["xy"][a + 1:b:2]
    sx[c] += sum(xs) / len(xs); sy[c] += sum(ys) / len(ys); sn[c] += 1
for i, c in enumerate(chome):
    c["cx"] = round(sx[i] / sn[i], 1) if sn[i] else None
    c["cy"] = round(sy[i] / sn[i], 1) if sn[i] else None
    c["napt"] = sn[i]

# 国勢調査2020（板橋区）の「住宅の建て方別 一般世帯人員」の共同住宅・階数別の人数に合わせて、
# 各建物の住民数を延べ床面積（底面積×階数）に比例して割り振る。
CENSUS_APT = {"1-2": 50677, "3-5": 150828, "6-10": 111983, "11+": 93976}
def grp(F):
    return "1-2" if F <= 2 else "3-5" if F <= 5 else "6-10" if F <= 10 else "11+"
FA = {k: 0.0 for k in CENSUS_APT}
for A_, F_ in zip(apt["A"], apt["F"]):
    FA[grp(F_)] += A_ * F_
res = [A_ * F_ / FA[grp(F_)] * CENSUS_APT[grp(F_)] for A_, F_ in zip(apt["A"], apt["F"])]
by = [0.0] * len(chome)
for c_, r_ in zip(apt["ch"], res):
    by[c_] += r_
cap = [min(1.0, 0.97 * c["pop"] / by[j]) if by[j] > 0 and c["pop"] else 1.0 for j, c in enumerate(chome)]
apt["R"] = [round(r_ * cap[c_], 1) for c_, r_ in zip(apt["ch"], res)]     # 町丁目の人口を超えないよう補正
apt["Rhi"] = [round(r_, 1) for r_ in res]                                  # 補正なし
print("chome capped:", sum(1 for x in cap if x < 1))

meta = d["meta"]
meta["censusApt"] = "総務省「令和2年国勢調査」住宅の建て方別住宅に住む一般世帯人員（板橋区の統計 第18表(3)）"
meta["census"] = "板橋区「令和7年版 板橋区の統計」第6表・第8表（住民基本台帳、令和8年1月1日現在）"
out_d = dict(meta=meta, chome=chome, apt=apt, ctx=ctx)
json.dump(out_d, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

nF = apt["F"]
print("apartments:", len(nF), " context:", len(ctx["h"]), " chome:", len(chome))
print("chome without census:", miss)
print("apt without chome:", sum(1 for c in apt["ch"] if c < 0))
print("roofArea from attribute:", sum(apt["Asrc"]), "/", len(nF))
print("apt >=3F:", sum(1 for f in nF if f >= 3), " 3-5F:", sum(1 for f in nF if 3 <= f <= 5), " >=6F:", sum(1 for f in nF if f >= 6))
print("apt with flood L2>0:", sum(1 for v in apt["fl"] if v and v > 0))
fh_ok = sum(1 for F, H in zip(nF, apt["H"]) if F and H and 2.5 <= H / F <= 4.5)
print("floor height in 2.5-4.5m:", fh_ok)
