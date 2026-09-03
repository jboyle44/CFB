import sys
import traceback

sys.path.insert(0, '.')

try:
    import weekly_update
    weekly_update.main()
    with open('../brr_diag_result.txt', 'w') as f:
        f.write("SUCCESS - no exception raised")
except Exception as e:
    with open('../brr_diag_result.txt', 'w') as f:
        f.write("EXCEPTION:\n")
        f.write(traceback.format_exc())
