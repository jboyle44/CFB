import sys, traceback
try:
    import runpy
    runpy.run_path("scripts/weekly_lines_update_nfl.py", run_name="__main__")
    result = "SUCCESS"
except Exception:
    result = traceback.format_exc()

with open('nfl_traceback_diag.txt', 'w') as f:
    f.write(result)
