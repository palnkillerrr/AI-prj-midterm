"""Correctness and wrapper regressions. Run: python -m unittest -v test_common"""
import math
import random
import time
import unittest
from dynamic_runner import episode, prepare
from benchmark_common import REGISTRY, check_heuristic, oracle, resolve, run_one, validate
from cases import common_cases, numeric_problem
from solvers import dfs_2_idastar as dfs


def bad_path(problem):
    return {"path": ["wrong"], "cost": 0, "expanded": 0, "extra": {}}


def crash(problem):
    raise RuntimeError("intentional test failure")


def mutate(problem):
    problem["graph"]["s"]["x"] = 1
    return {"path": ["s"], "cost": 0, "expanded": 1, "extra": {}}


def slow(problem):
    time.sleep(1)
    return {"path": ["s"], "cost": 0, "expanded": 1, "extra": {}}


_calls = 0


def nondeterministic(problem):
    global _calls
    _calls += 1
    return {"path": ["s"], "cost": 0, "expanded": _calls, "extra": {}}


class SolverTests(unittest.TestCase):
    def test_shared_inputs_and_optimality(self):
        for t in common_cases():
            p = numeric_problem(t)
            ref = oracle(p)
            check_heuristic(p)
            for name, spec in REGISTRY.items():
                with self.subTest(test=t["test_id"], algorithm=name):
                    r = resolve(spec)(p)
                    validate(r, p, ref, name != "DFS")
                    if p["start"] == p["goal"]:
                        self.assertEqual(r["expanded"], 1)
                        self.assertGreaterEqual(r["extra"]["peak_frontier"], 1)

    def test_flood_compilation_preserves_cost_and_node_counts(self):
        for t in dfs.get_tests(False)[:6]:
            raw = dfs.problem_from_test(t)
            p = numeric_problem(t)
            for u, nb in raw.graph.items():
                for v in nb:
                    self.assertEqual(raw.step_cost(u, v, v), p["graph"][u][v])
            for fn in (dfs.solve_dfs, dfs.solve_ida_star, dfs.solve_astar_reference):
                a, b = fn(raw), fn(p)
                self.assertEqual((a["path"], a["cost"], a["expanded"]), (b["path"], b["cost"], b["expanded"]))

    def test_ida_goal_in_peak_path(self):
        p = {"graph": {"s": {"t": 1}, "t": {}}, "start": "s", "goal": "t"}
        r = dfs.solve(p)
        self.assertEqual(r["extra"]["peak_frontier"], 2)

    def test_first_meeting_is_not_stopping(self):
        p = {"graph": {"s": {"a": 1, "b": 2}, "a": {"t": 100}, "b": {"t": 2}, "t": {}},
             "start": "s", "goal": "t"}
        validate(resolve(REGISTRY["Bi-UCS"])(p), p, 4, True)

    def test_directed_zero_float_and_mixed_labels_random(self):
        rnd = random.Random(16102026)
        for i in range(300):
            n = rnd.randint(2, 8)
            labels = ["s", ("t", 1)] + list(range(n - 2))
            g = {u: {} for u in labels}
            for u in labels:
                for v in labels:
                    if u != v and rnd.random() < .24:
                        g[u][v] = rnd.choice([0, .1, 1, 2.5, math.inf])
            p = {"graph": g, "start": labels[0], "goal": labels[1]}
            ref = oracle(p)
            for name, spec in REGISTRY.items():
                with self.subTest(i=i, name=name):
                    validate(resolve(spec)(p), p, ref, name != "DFS")

    def test_validator_rejects_invalid_results(self):
        p = {"graph": {"s": {"t": math.inf}, "t": {}}, "start": "s", "goal": "t"}
        for r in [dict(path=["s", "t"], cost=math.inf, expanded=1, extra={}),
                  dict(path=[], cost=0, expanded=1, extra={}),
                  dict(path=None, cost=0, expanded=1, extra={}),
                  dict(path=None, cost=math.inf, expanded=True, extra={}),
                  dict(path=None, cost=math.inf, expanded=1, extra=[]),
                  dict(path=None, cost=math.nan, expanded=1, extra={})]:
            with self.assertRaises(ValueError):
                validate(r, p, math.inf, True)
        q = {"graph": {"s": {"t": 1}, "t": {}}, "start": "s", "goal": "t"}
        with self.assertRaises(ValueError):
            validate(dict(path=None, cost=math.inf, expanded=1, extra={}), q, 1, False)

    def test_invalid_cost_input_and_heuristic(self):
        for w in (-1, math.nan):
            with self.assertRaises(ValueError):
                numeric_problem({"graph": {"s": {"t": w}}, "start": "s", "goal": "t"})
        with self.assertRaises(ValueError):
            check_heuristic({"graph": {"s": {"t": 1}, "t": {}}, "start": "s", "goal": "t",
                             "locations": {"s": (0, 0), "t": (10, 0)}})


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.p = {"graph": {"s": {}}, "start": "s", "goal": "s"}

    def test_success_and_samples(self):
        r = run_one(REGISTRY["UCS"], self.p, 0, True, 2, 15)
        self.assertEqual(r["status"], "PASS", r)
        self.assertEqual(len(r["samples"]), 2)
        self.assertGreater(r["memory_kb"], 0)
        self.assertGreater(r["time_ms"], 0)

    def test_failures_are_not_performance_rows(self):
        for fn in ("bad_path", "crash", "mutate", "nondeterministic"):
            r = run_one("test_common:" + fn, self.p, 0, True, 2, 15)
            self.assertEqual(r["status"], "FAILED", r)
            self.assertNotIn("time_ms", r)
            self.assertNotIn("memory_kb", r)

    def test_timeout_is_explicit_failure(self):
        r = run_one("test_common:slow", self.p, 0, True, 1, .2)
        self.assertEqual(r["status"], "FAILED", r)
        self.assertIn("TIMEOUT", r["reason"])


class DynamicHookTests(unittest.TestCase):
    def test_retained_object_and_phase_costs_with_test_stub(self):
        # This stub tests the runner lifecycle only. It is deliberately NOT D* Lite.
        made = []
        class TestPlanner:
            def __init__(self, p):
                self.p, self.calls = p, 0
                made.append(self)
            def update(self, changes):
                for edge in changes:
                    self.p["graph"][edge["u"]][edge["v"]] = math.inf if edge["cost"] == "inf" else edge["cost"]
            def plan(self):
                self.calls += 1
                return dfs.solve_astar_reference(self.p)
        scenario = {"base_test_id": "common_romania_flood42", "updates": [
            {"edges": [{"u": "Rimnicu", "v": "Pitesti", "cost": "inf"},
                       {"u": "Pitesti", "v": "Rimnicu", "cost": "inf"}]}]}
        snapshots, changes = prepare(scenario)
        rows = episode(TestPlanner, snapshots, changes)
        baseline = episode(None, snapshots, changes, use_reference=True)
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0].calls, 2)
        self.assertEqual([r["cost"] for r in rows], [r["cost"] for r in baseline])
        self.assertEqual([r["phase"] for r in rows], ["initial", "repair_1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
