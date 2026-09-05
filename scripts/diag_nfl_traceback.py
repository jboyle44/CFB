import sys, traceback
sys.path.insert(0, '.')
try:
    import weekly_lines_update_nfl
    weekly_lines_update_nfl.main()
    result = "SUCCESS"
except Exception:
    result = traceback.format_exc()

with open('../nfl_traceback_diag.txt', 'w') as f:
    f.write(result)
