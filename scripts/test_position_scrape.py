import sys
sys.path.insert(0, '.')
from scrape_teamcrafters import get_cfb27_ratings

ratings = get_cfb27_ratings(701)  # Ohio State
with open('../position_test_result.txt', 'w') as f:
    for name in ['jeremiah smith', 'julian sayin', 'kenyatta jackson jr.', 'terry moore', 'bo jackson']:
        info = ratings.get(name)
        f.write(f"{name!r}: {info}\n")
