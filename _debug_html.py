"""
Quick debug script: extract __NEXT_DATA__ from saved raw HTML
and print the merchant structure to help tune the scraper.

Usage: python3 _debug_html.py [path/to/file.html]
"""
import json, re, sys

path = sys.argv[1] if len(sys.argv) > 1 else None
if not path:
    import glob
    files = sorted(glob.glob("data/raw/grabfood_*.html"))
    if not files:
        print("No raw HTML files found in data/raw/")
        sys.exit(1)
    path = files[-1]

print(f"Reading: {path}")
html = open(path, encoding="utf-8").read()
print(f"Size: {len(html):,} bytes")

m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
if not m:
    print("__NEXT_DATA__ NOT FOUND in HTML")
    sys.exit(1)

data = json.loads(m.group(1))
page_props = data.get("props", {}).get("pageProps", {})
print(f"\nTop-level pageProps keys ({len(page_props)}): {list(page_props.keys())[:20]}")

# Walk one more level
for k, v in list(page_props.items())[:15]:
    if isinstance(v, dict):
        sub = list(v.keys())[:8]
        print(f"  .{k} (dict, {len(v)} keys): {sub}")
    elif isinstance(v, list):
        item0_keys = list(v[0].keys())[:8] if v and isinstance(v[0], dict) else "—"
        print(f"  .{k} (list, len={len(v)}), first item keys: {item0_keys}")
    else:
        print(f"  .{k} = {str(v)[:80]}")

# Look for anything with merchantID
def find_merchants(obj, path="", depth=0):
    if depth > 6:
        return
    if isinstance(obj, dict):
        if "merchantID" in obj or "displayName" in obj:
            print(f"\n*** Merchant found at: {path}")
            print(json.dumps({k: obj[k] for k in list(obj.keys())[:10]}, ensure_ascii=False, indent=2)[:600])
            return
        for k, v in obj.items():
            find_merchants(v, f"{path}.{k}", depth+1)
    elif isinstance(obj, list) and obj:
        find_merchants(obj[0], f"{path}[0]", depth+1)

find_merchants(page_props)


