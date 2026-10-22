"""Run every integration regression. Python standard library only."""
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    suite=unittest.defaultTestLoader.discover(str(ROOT),pattern='test_*.py',top_level_dir=str(ROOT))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'skipped':len(result.skipped),'success':result.wasSuccessful(),
            'static_random_graphs':300,'static_solvers':7,
            'dynamic_random_episodes':300,'dynamic_phases_per_episode':10}
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'results/selftest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)