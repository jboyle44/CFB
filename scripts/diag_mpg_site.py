import requests, re
resp = requests.get("https://mpg000f.github.io/cbb_power_rating/", timeout=20)
text = resp.text
output = []
for kw in ["change", "delta", "prevWeek", "previous", "lastWeek", "diff"]:
    idx = text.lower().find(kw.lower())
    if idx != -1:
        output.append(f"'{kw}' found at index {idx}: ...{text[max(0,idx-100):idx+200]}...")
    else:
        output.append(f"'{kw}' not found")
with open('../mpg_change_search.txt', 'w') as f:
    f.write("\n\n".join(output))
