import sys, json
sys.path.insert(0, 'scripts')
import weekly_lines_update as m

# Load current data and find the Massachusetts@Rutgers record specifically
with open('lines_data.json') as f:
    raw = json.load(f)
games_data = raw.get('games', raw)
target = next(g for g in games_data if g['homeTeam']=='Rutgers' and g['awayTeam']=='Massachusetts')

output = [f"BEFORE: status={target['status']}, atsResult={target.get('atsResult')}, vegasSpread={target.get('vegasSpread')}, modelCorrect={target.get('modelCorrect')}"]

# Simulate calling apply_line_and_grade directly on this exact record
result = m.apply_line_and_grade(dict(target), None)
output.append(f"AFTER apply_line_and_grade: status={result['status']}, atsResult={result.get('atsResult')}, modelCorrect={result.get('modelCorrect')}")

with open('grading_diag.txt', 'w') as f:
    f.write("\n".join(output))
