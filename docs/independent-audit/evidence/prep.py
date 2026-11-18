import csv, sys, hashlib
src, dst = sys.argv[1], sys.argv[2]
rows = []
with open(src, newline="") as f:
    for r in csv.DictReader(f):
        p = r.get("PriceUSD", "")
        if not p:
            continue
        v = float(p)
        if v > 0:
            rows.append((r["time"][:10] + "T00:00:00+00:00", v))
with open(dst, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["timestamp", "close"]); w.writerows(rows)
print(dst, len(rows), rows[0], rows[-1], hashlib.sha256(open(src,'rb').read()).hexdigest())
