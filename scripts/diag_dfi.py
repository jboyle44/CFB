import sys
import traceback
sys.path.insert(0, '.')

try:
    import weekly_lines_update
    weekly_lines_update.main()
    with open('../dfi_diag_result.txt', 'w') as f:
        f.write("SUCCESS")
except Exception as e:
    with open('../dfi_diag_result.txt', 'w') as f:
        f.write("EXCEPTION:\n")
        f.write(traceback.format_exc())
