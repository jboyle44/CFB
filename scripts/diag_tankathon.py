import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

url = "https://www.tankathon.com/nfl/big-board"
resp = requests.get(url, headers=HEADERS, timeout=20)

output = [f"status: {resp.status_code}", f"length: {len(resp.text)}"]

soup = BeautifulSoup(resp.text, "html.parser")

# Look for any repeating structural pattern - divs with player-like classes
all_classes = set()
for tag in soup.find_all(class_=True):
    for c in tag.get('class', []):
        all_classes.add(c)
output.append(f"Total unique classes found: {len(all_classes)}")
player_related = sorted([c for c in all_classes if any(k in c.lower() for k in ['player', 'rank', 'row', 'card', 'prospect'])])
output.append(f"Player/rank-related classes: {player_related}")

with open('../tankathon_diag.txt', 'w') as f:
    f.write("\n".join(output))
    f.write("\n\n=== RAW HTML SNIPPET (first 5000 chars after body) ===\n")
    body = soup.find('body')
    if body:
        f.write(str(body)[:8000])
