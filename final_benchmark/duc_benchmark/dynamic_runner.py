"""Stateful A* / D* Lite benchmark with per-phase correctness and process timeout.

python dynamic_runner.py --suite all --full
D* Lite's adapter is retained across all phases. Each repetition is a fresh
whole episode. Initial time includes factory/clone/index creation; repair time
includes update + move_start + search + path extraction. Input snapshots, input
copies, oracle and validation are excluded from timing. tracemalloc stays on
for the episode, so repair peaks include retained planner state and prior phase
outputs. Small harness bookkeeping is included, equally for both algorithms.
"""
import argparse
import copy
import csv
import gc
import hashlib
import json
import math
import platform
import statistics
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

from benchmark_common import check_heuristic, oracle, resolve, save_json, validate, run_isolated, json_safe
from cases import common_cases, numeric_problem, fingerprint
from solvers import astar_to_dstarlite as member
from solvers.dfs_2_idastar import solve_astar_reference


def prepare(scenario):
    if 'member_test_id' in scenario:
        test = next(t for t in member.get_tests(full=True) if t['test_id'] == scenario['member_test_id'])
        current = copy.deepcopy(test)
        snapshots, changes_by_phase = [numeric_problem(current)], [[]]
        for event in test['dynamic_updates']:
            old = snapshots[-1]
            for (u, v), flood in event.get('flood_changes', {}).items():
                # Member events are physical roads: update both existing directions.
                for a, b in ((u, v), (v, u)):
                    if b in current['graph'].get(a, {}):
                        current['graph'][a][b]['flood'] = flood
            if event.get('new_start') is not None:
                current['start'] = event['new_start']
            new = numeric_problem(current)
            changes = [{'u': u, 'v': v, 'cost': w}
                       for u, nb in new['graph'].items() for v, w in nb.items()
                       if old['graph'].get(u, {}).get(v) != w]
            snapshots.append(new)
            changes_by_phase.append(changes)
    else:
        test = next(t for t in common_cases() if t['test_id'] == scenario['base_test_id'])
        snapshots, changes_by_phase = [numeric_problem(test)], [[]]
        for update in scenario['updates']:
            p = copy.deepcopy(snapshots[-1])
            changes = copy.deepcopy(update['edges'])
            for edge in changes:
                w = math.inf if edge['cost'] == 'inf' else edge['cost']
                if isinstance(w, bool) or not isinstance(w, (float, int)) or math.isnan(w) or w < 0:
                    raise ValueError('Invalid dynamic edge cost')
                p['graph'].setdefault(edge['u'], {})[edge['v']] = w
            if 'start' in update:
                p['start'] = update['start']
            snapshots.append(p)
            changes_by_phase.append(changes)
    for p in snapshots:
        check_heuristic(p)
    return snapshots, changes_by_phase


def episode(factory, snapshots, changes, use_reference=False, baseline=None, measured=True):
    refs = [oracle(p) for p in snapshots]
    fresh = [copy.deepcopy(p) for p in snapshots]
    planner_input = copy.deepcopy(snapshots[0])
    phase_changes = copy.deepcopy(changes)
    baseline = baseline or solve_astar_reference
    results = [None] * len(fresh)
    measurements = [None] * len(fresh)
    planner = None
    gc.collect()
    if measured:
        tracemalloc.start()
    try:
        for i, p in enumerate(fresh):
            if measured:
                tracemalloc.reset_peak()
                retained = tracemalloc.get_traced_memory()[0]
            start = time.perf_counter()
            if use_reference:
                result = baseline(p)
            else:
                if i == 0:
                    planner = factory(planner_input)
                else:
                    planner.update(phase_changes[i])
                    if p['start'] != fresh[i-1]['start']:
                        planner.move_start(p['start'])
                result = planner.plan()
            elapsed = (time.perf_counter() - start) * 1000
            peak = tracemalloc.get_traced_memory()[1] if measured else 0
            # Validation follows stop(), so its allocations cannot pollute repair peaks.
            measurements[i] = (elapsed, peak/1024, retained/1024 if measured else 0)
            results[i] = result
        if measured:
            tracemalloc.stop()
    finally:
        if measured and tracemalloc.is_tracing():
            tracemalloc.stop()
    rows = []
    for i, (p, result, (elapsed, peak, retained)) in enumerate(zip(snapshots, results, measurements)):
        validate(result, p, refs[i], True)
        if fingerprint(fresh[i]) != fingerprint(p):
            raise ValueError('Baseline mutated a snapshot')
        rows.append(dict(result, phase='initial' if i == 0 else f'repair_{i}', status='PASS',
                         time_ms=elapsed, memory_kb=peak, retained_before_kb=retained))
    return rows


def _episode_job(adapter, baseline, snapshots, changes, repetitions):
    factory, solver = resolve(adapter), resolve(baseline) if baseline else None
    preflight = episode(factory, snapshots, changes, bool(baseline), solver, measured=False)
    episodes = [episode(factory, snapshots, changes, bool(baseline), solver) for _ in range(repetitions)]
    for ep in episodes:
        if any((r['cost'], r['expanded']) != (ref['cost'], ref['expanded']) for r, ref in zip(ep, preflight)):
            raise ValueError('Nondeterministic phase cost/expanded')
    return episodes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', default='dstar_adapter:create_planner')
    parser.add_argument('--baseline', default='solvers.astar_to_dstarlite:solve_astar')
    parser.add_argument('--scenario', type=Path, default=Path(__file__).parent/'dynamic_scenario.json')
    parser.add_argument('--suite', choices=('scenario', 'member', 'all'), default='scenario')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--heavy-repetitions', type=int, default=1)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--out', type=Path, default=Path(__file__).parent/'results/dynamic.json')
    args = parser.parse_args()
    if min(args.repetitions, args.heavy_repetitions, args.timeout) <= 0:
        parser.error('Repetitions and timeout must be positive')
    scenarios = []
    if args.suite in ('scenario','all'):
        scenarios.append(dict(json.loads(args.scenario.read_text(encoding='utf-8')), test_id='integration_romania',
                              category='INTEGRATION', source='Duc integration scenario, not teacher baseline'))
    if args.suite in ('member','all'):
        scenarios.extend(dict(member_test_id=t['test_id'], test_id=t['test_id'], category=t['category'],
                              source='Phuong Anh original dynamic generator', description=t['description'])
                         for t in member.get_tests(args.full) if t.get('dynamic_updates'))
    rows, raw, totals, manifest = [], {}, [], []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        snapshots, changes = prepare(scenario)
        tid = scenario['test_id']
        reps = args.heavy_repetitions if scenario['category'] == 'STRESS' else args.repetitions
        manifest.append(dict(scenario, phase_sha256=[fingerprint(p) for p in snapshots], repetitions=reps))
        raw[tid] = {}
        for name, baseline in (('A* (rerun)', args.baseline), ('D* Lite', None)):
            episodes = run_isolated('dynamic_runner:_episode_job',
                                   (args.adapter, baseline, snapshots, changes, reps), args.timeout)
            if isinstance(episodes, dict):
                rows.append(dict(episodes, test_id=tid, algorithm=name, repetitions=reps))
                print(f'{tid} | {name} | FAILED | {episodes.get("reason")}', flush=True)
                continue
            raw[tid][name] = episodes
            for i in range(len(snapshots)):
                sample = episodes[0][i]
                rows.append(dict(sample, test_id=tid, algorithm=name, category=scenario['category'], repetitions=reps,
                                 optimal_cost=oracle(snapshots[i]), input_sha256=fingerprint(snapshots[i]),
                                 time_ms=statistics.median(ep[i]['time_ms'] for ep in episodes),
                                 time_ms_min=min(ep[i]['time_ms'] for ep in episodes),
                                 time_ms_max=max(ep[i]['time_ms'] for ep in episodes),
                                 memory_kb=statistics.median(ep[i]['memory_kb'] for ep in episodes)))
            for label, indices in (('episode', range(len(snapshots))), ('repairs', range(1,len(snapshots)))):
                ts = [sum(ep[i]['time_ms'] for i in indices) for ep in episodes]
                totals.append(dict(test_id=tid, algorithm=name, scope=label, repetitions=reps,
                                   expanded=sum(episodes[0][i]['expanded'] for i in indices),
                                   time_ms=statistics.median(ts),
                                   memory_kb=statistics.median(max(ep[i]['memory_kb'] for i in indices) for ep in episodes)))
            print(f'{tid} | {name} | {len(snapshots)} phases PASS | expanded={sum(r["expanded"] for r in episodes[0])}',flush=True)
        save_json(args.out, {'metadata': {'created_utc': datetime.now(timezone.utc).isoformat(), 'python':sys.version,
                    'platform':platform.platform(), 'adapter':args.adapter, 'baseline':args.baseline,
                    'repetitions':args.repetitions, 'heavy_repetitions':args.heavy_repetitions,
                    'timeout_seconds_per_episode_job':args.timeout,
                    'memory_definition':'peak traced Python allocations including retained planner state, prior phase outputs and small harness bookkeeping',
                    'time_definition':'factory + plan for initial; update + move_start + plan for repair; tracemalloc ON',
                    'domain':'D* Lite dynamic adapter requires strictly positive finite costs; +inf permitted',
                    'solver_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (Path(__file__).parent/'solvers'/'astar_to_dstarlite.py',Path(__file__).parent/'dstar_adapter.py')}},
                    'manifest':manifest,'rows':rows,'totals':totals,'raw_episodes':raw})
        fields=['test_id','phase','algorithm','category','status','reason','cost','optimal_cost','expanded','time_ms',
                'time_ms_min','time_ms_max','memory_kb','repetitions','input_sha256']
        with args.out.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fields,extrasaction='ignore');writer.writeheader();writer.writerows(json_safe(rows))
    failed=[r for r in rows if r['status']!='PASS']
    print(f'Completed: {len(rows)-len(failed)}/{len(rows)} phase rows PASS; {len(failed)} FAILED')
    return int(bool(failed))


if __name__ == '__main__':
    raise SystemExit(main())