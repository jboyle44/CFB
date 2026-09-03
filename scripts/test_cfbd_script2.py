import sys
sys.path.insert(0, '.')
from build_depth_chart import build
result = build('ohio-state', '../test_real_output.json')
