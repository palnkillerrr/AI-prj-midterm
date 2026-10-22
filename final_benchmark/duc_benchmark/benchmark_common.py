"""Duc's benchmark wrapper. Python 3.10+, standard library only.

python benchmark_common.py --suite common
python benchmark_common.py --suite all --full --repetitions 7 --heavy-repetitions 1
python benchmark_common.py --plugins plugins.json

Main measurements use perf_counter AND tracemalloc in the same execution.
Input construction, validation, oracle, process startup and deepcopy are excluded.
Bi-UCS reverse-graph construction remains inside solve and is included.
"""
import argparse
import copy
import csv
import gc
import hashlib
import heapq
import importlib
import itertools
import json
import math
import pickle
import subprocess
import uuid
from contextlib import contextmanager
import platform
import statistics
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

from cases import fingerprint, numeric_problem, select_cases

REGISTRY = {
    "A*": "solvers.astar_to_dstarlite:solve_astar",
    "D* Lite": "solvers.astar_to_dstarlite:solve",
    "DFS": "solvers.dfs_2_idastar:solve_dfs",
    "IDA*": "solvers.dfs_2_idastar:solve_ida_star",
    "UCS": "solvers.ucs_biucs_benchmark:solve_ucs",
    "Bi-UCS": "solvers.ucs_biucs_benchmark:solve_biucs",
    "A* (ref)": "solvers.dfs_2_idastar:solve_astar_reference",
}


def oracle(problem):
    """Independent Dijkstra, supports heterogeneous node types and blocked edges."""
    dist, serial = {problem["start"]: 0}, itertools.count()
    queue = [(0, next(serial), problem["start"])]
    while queue:
        d, _, u = heapq.heappop(queue)
        if d != dist.get(u):
            continue
        if u == problem["goal"]:
            return d
        for v, w in problem["graph"].get(u, {}).items():
            if not math.isfinite(w):
                continue
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                heapq.heappush(queue, (nd, next(serial), v))
    return math.inf


def check_heuristic(problem):
    loc = problem.get("locations")
    if loc is None:
        return "h=0 (no coordinates)"
    nodes = set(problem["graph"]) | {v for nb in problem["graph"].values() for v in nb}
    if not nodes.issubset(loc):
        raise ValueError("Missing heuristic coordinates")
    for u, nb in problem["graph"].items():
        for v, w in nb.items():
            if math.dist(loc[u], loc[v]) > w + 1e-9:
                raise ValueError(f"Euclidean edge consistency fails: {u!r}->{v!r}")
    return "Euclidean; edge consistency verified"


def validate(result, problem, optimal, require_optimal):
    if not isinstance(result, dict) or not {"path", "cost", "expanded", "extra"}.issubset(result):
        raise ValueError("Missing common result fields")
    path, cost, expanded, extra = (result[k] for k in ("path", "cost", "expanded", "extra"))
    if isinstance(expanded, bool) or not isinstance(expanded, int) or expanded < 0:
        raise ValueError("expanded must be an integer >= 0")
    if not isinstance(extra, dict):
        raise ValueError("extra must be a dictionary")
    if isinstance(cost, bool) or not isinstance(cost, (float, int)) or math.isnan(cost) or cost < 0:
        raise ValueError("Invalid returned cost")
    if path is None:
        if cost != math.inf or optimal != math.inf:
            raise ValueError("False no-solution result")
    else:
        if not isinstance(path, list) or not path or path[0] != problem["start"] or path[-1] != problem["goal"]:
            raise ValueError("Path endpoints/type invalid")
        total = 0
        for u, v in zip(path, path[1:]):
            if v not in problem["graph"].get(u, {}):
                raise ValueError("Path contains nonexistent arc")
            w = problem["graph"][u][v]
            if not math.isfinite(w):
                raise ValueError("Path crosses blocked arc")
            total += w
        if not math.isfinite(cost) or not math.isclose(cost, total, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("Returned cost differs from path cost")
        if require_optimal and not math.isclose(cost, optimal, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("Suboptimal result from optimal solver")
    if "expanded_forward" in extra and "expanded_backward" in extra:
        if expanded != extra["expanded_forward"] + extra["expanded_backward"]:
            raise ValueError("Bidirectional counters do not sum to expanded")


def resolve(spec):
    module, name = spec.split(":", 1)
    fn = getattr(importlib.import_module(module), name)
    if not callable(fn):
        raise TypeError("Plugin must reference a callable")
    return fn


def worker(conn, spec, problem, optimal, require_optimal, repetitions):
    try:
        solver = resolve(spec)
        original_hash = fingerprint(problem)
        preflight = copy.deepcopy(problem)
        first = solver(preflight)
        validate(first, problem, optimal, require_optimal)
        if fingerprint(preflight) != original_hash:
            raise ValueError("Solver mutates input during preflight")
        samples = []
        for _ in range(repetitions):
            fresh = copy.deepcopy(problem)
            gc.collect()
            tracemalloc.start()
            try:
                start = time.perf_counter()
                result = solver(fresh)
                elapsed = (time.perf_counter() - start) * 1000
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            validate(result, problem, optimal, require_optimal)
            if fingerprint(fresh) != original_hash:
                raise ValueError("Solver mutates input during timed run")
            if result["expanded"] != first["expanded"] or result["cost"] != first["cost"]:
                raise ValueError("Cost/expanded changes between repetitions")
            samples.append({"time_ms": elapsed, "memory_kb": peak / 1024,
                            "cost": result["cost"], "expanded": result["expanded"]})
            # Keep only the first output alive consistently across solvers.
            del result, fresh
        times = [s["time_ms"] for s in samples]
        mems = [s["memory_kb"] for s in samples]
        conn.send({"status": "PASS", "reason": "path/cost/oracle validated in every run",
                   "cost": first["cost"], "expanded": first["expanded"], "path": first["path"],
                   "extra": first["extra"], "time_ms": statistics.median(times),
                   "time_ms_min": min(times), "time_ms_max": max(times),
                   "memory_kb": statistics.median(mems), "memory_kb_max": max(mems),
                   "samples": samples})
    except BaseException as exc:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        conn.send({"status": "FAILED", "reason": f"{type(exc).__name__}: {exc}"})
    finally:
        conn.close()


class _ResultSink:
    def send(self, result):
        self.value = result
    def close(self):
        pass


def _static_job(spec, problem, optimal, require_optimal, repetitions):
    sink = _ResultSink()
    worker(sink, spec, problem, optimal, require_optimal, repetitions)
    return sink.value


@contextmanager
def _job_files():
    folder = Path(__file__).resolve().parent / ".worker-temp"
    folder.mkdir(exist_ok=True)
    token = uuid.uuid4().hex
    paths = tuple(folder / (token + suffix) for suffix in (".request", ".response", ".log"))
    try:
        yield paths
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


def run_isolated(call, args, timeout):
    """Private, locally generated pickle files avoid Windows named-pipe restrictions.

    A fresh interpreter handles each job. Startup, transport and serialization
    remain outside solver measurements, and inside the whole-job timeout.
    """
    with _job_files() as (request, response, log):
        request.write_bytes(pickle.dumps((call, args), protocol=pickle.HIGHEST_PROTOCOL))
        command = [sys.executable, str(Path(__file__).resolve()), "--_worker", str(request), str(response)]
        try:
            with log.open("wb") as stream:
                proc = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "FAILED", "reason": f"TIMEOUT after {timeout:g}s (preflight + repetitions)"}
        if proc.returncode or not response.exists():
            detail = log.read_text(encoding="utf-8", errors="replace")[-2000:]
            return {"status": "FAILED", "reason": f"Worker exited {proc.returncode}: {detail}"}
        return pickle.loads(response.read_bytes())


def _subprocess_entry(request, response):
    # Only run_isolated's private temporary files are accepted by this internal CLI.
    try:
        call, args = pickle.loads(Path(request).read_bytes())
        result = resolve(call)(*args)
    except BaseException as exc:
        result = {"status": "FAILED", "reason": f"{type(exc).__name__}: {exc}"}
    Path(response).write_bytes(pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL))


def run_one(spec, problem, optimal, require_optimal, repetitions, timeout):
    return run_isolated("benchmark_common:_static_job",
                        (spec, problem, optimal, require_optimal, repetitions), timeout)


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return "inf" if value > 0 else "-inf"
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def save_json(path, value):
    path.write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def export(outdir, rows, metadata, manifest):
    outdir.mkdir(parents=True, exist_ok=True)
    save_json(outdir / "benchmark.json", {"metadata": metadata, "rows": rows})
    save_json(outdir / "manifest.json", manifest)
    fields = ["test_id", "category", "algorithm", "status", "reason", "cost", "optimal_cost", "expanded",
              "time_ms", "time_ms_min", "time_ms_max", "memory_kb", "memory_kb_max", "repetitions", "input_sha256"]
    with (outdir / "benchmark.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(json_safe(rows))
    columns = ["Test", "Algorithm", "Status", "Cost", "Expanded", "Time ms", "Peak KB"]
    lines = ["COMMON BENCHMARK", "Time and peak Python allocations measured together with tracemalloc ON.",
             "Time/Memory = median of per-run samples; peak bytes / 1024 (KiB, labelled KB per spec).", "",
             " | ".join(columns)]
    for r in rows:
        values = [r["test_id"], r["algorithm"], r["status"], r.get("cost", "-"), r.get("expanded", "-"),
                  f'{r["time_ms"]:.4f}' if "time_ms" in r else "-",
                  f'{r["memory_kb"]:.2f}' if "memory_kb" in r else "-"]
        lines.append(" | ".join(map(str, values)))
        if r["status"] != "PASS":
            lines.append("  Reason: " + r["reason"])
    (outdir / "benchmark.txt").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("common", "submitted", "all"), default="common")
    parser.add_argument("--full", action="store_true", help="Include original optional DFS 8x8 tests")
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--heavy-repetitions", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--plugins", type=Path, help="JSON object of name: module:function static solvers")
    args = parser.parse_args()
    if min(args.repetitions, args.heavy_repetitions, args.timeout) <= 0:
        parser.error("Repetitions and timeout must be positive")
    registry = dict(REGISTRY)
    if args.plugins:
        plugins = json.loads(args.plugins.read_text(encoding="utf-8"))
        for name, spec in plugins.items():
            resolve(spec)
            if name in registry:
                parser.error(f"Plugin would replace existing solver: {name}")
        registry.update(plugins)
    tests = select_cases(args.suite, args.full)
    rows, manifest = [], []
    for t in tests:
        p = numeric_problem(t)
        ref = oracle(p)
        h = check_heuristic(p)
        sha = fingerprint(p)
        # Deliberately fixed before observing timings, same repeats for each solver in a test.
        heavy = t["category"] == "STRESS" or "worst_grid6" in t["test_id"] or "worst_grid7" in t["test_id"] or "worst_grid8" in t["test_id"]
        reps = args.heavy_repetitions if heavy else args.repetitions
        manifest.append({"test_id": t["test_id"], "category": t["category"], "source": t["source"],
                         "description": t["description"], "start": repr(p["start"]), "goal": repr(p["goal"]),
                         "nodes": len(p["graph"]), "arcs": sum(map(len, p["graph"].values())),
                         "blocked_arcs": sum(not math.isfinite(w) for nb in p["graph"].values() for w in nb.values()),
                         "heuristic": h, "optimal_cost": ref, "input_sha256": sha, "repetitions": reps})
        names = list(t["algorithms"])
        if t["source"] == "shared_v1":
            names.extend(name for name in registry if name not in REGISTRY)
        for name in names:
            r = run_one(registry[name], p, ref, name != "DFS", reps, args.timeout)
            r.update(test_id=t["test_id"], category=t["category"], algorithm=name,
                     optimal_cost=ref, repetitions=reps, input_sha256=sha)
            rows.append(r)
            print(f'{t["test_id"]} | {name} | {r["status"]} | expanded={r.get("expanded", "-")}', flush=True)
        metadata = {"created_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                    "platform": platform.platform(), "processor": platform.processor(),
                    "metric_mode": "perf_counter + tracemalloc in same solve call; median",
                    "input_setup_excluded": True, "reverse_graph_included_for_biucs": True,
                    "timeout_seconds_per_job": args.timeout, "suite": args.suite, "full": args.full,
                    "repetitions": args.repetitions, "heavy_repetitions": args.heavy_repetitions,
                    "solver_sha256": {str(f.relative_to(Path(__file__).parent)): hashlib.sha256(f.read_bytes()).hexdigest()
                                      for f in (Path(__file__).parent / "solvers").glob("*.py")},
                    "worker_transport": "private temporary files; fresh subprocess per job",
                    "pending": []}
        export(args.out, rows, metadata, manifest)  # checkpoint after every input
    failed = [r for r in rows if r["status"] != "PASS"]
    print(f'Completed: {len(rows)-len(failed)}/{len(rows)} PASS; {len(failed)} FAILED')
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--_worker":
        _subprocess_entry(sys.argv[2], sys.argv[3])
    else:
        sys.exit(main())
