import requests
resp = requests.get("https://mpg000f.github.io/cbb_power_rating/", timeout=20)
with open('../mpg_site_diag.txt', 'w') as f:
    f.write(f"status: {resp.status_code}\n")
    f.write(f"length: {len(resp.text)}\n\n")
    # Look for "Ohio State" context to see what's around it
    idx = resp.text.find("Ohio State")
    if idx != -1:
        f.write("Context around Ohio State:\n")
        f.write(resp.text[max(0,idx-500):idx+1000])
