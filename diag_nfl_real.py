import subprocess
result = subprocess.run(["python3", "scripts/weekly_lines_update_nfl.py"], capture_output=True, text=True)
with open('nfl_traceback_diag.txt', 'w') as f:
    f.write(f"returncode={result.returncode}\n")
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr)
