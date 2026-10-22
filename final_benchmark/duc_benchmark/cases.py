"""Shared inputs and unchanged member test generators. No solver-specific graph edits."""
import hashlib
import json
import math
from solvers import dfs_2_idastar as dfs
from solvers import ucs_biucs_benchmark as ucs
from solvers import astar_to_dstarlite as dst

ALL = ("DFS", "IDA*", "UCS", "Bi-UCS", "A* (ref)", "A*", "D* Lite")


def numeric_problem(test):
    """Compile flood costs once for every solver; keep blocked arcs as +inf."""
    graph = {}
    for u, nbrs in test["graph"].items():
        graph[u] = {}
        for v, edge in nbrs.items():
            if isinstance(edge, dict):
                d, f = edge["distance"], edge["flood"]
                cv, alpha = test.get("C_v", 60), test.get("alpha", 2)
                if cv <= 0 or alpha < 0 or d < 0 or f < 0:
                    raise ValueError("Invalid flood-model parameters")
                w = math.inf if f >= cv else d * (1 + alpha * (f / cv))
            else:
                w = edge
            if isinstance(w, bool) or not isinstance(w, (int, float)) or math.isnan(w) or w < 0:
                raise ValueError("Costs must be nonnegative numbers; +inf denotes blocked arcs")
            graph[u][v] = w
    p = {"graph": graph, "start": test["start"], "goal": test["goal"]}
    if test.get("locations") is not None:
        p["locations"] = test["locations"]
    return p


def fingerprint(problem):
    # Include neighbour order: it affects DFS and FIFO tie-breaking.
    payload = ([(repr(u), [(repr(v), repr(w)) for v, w in nb.items()])
                for u, nb in problem["graph"].items()],
               repr(problem["start"]), repr(problem["goal"]),
               [(repr(u), list(xy)) for u, xy in problem.get("locations", {}).items()])
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


def common_cases():
    submitted = dfs.get_tests(full=False)
    flood, blocked = submitted[0], submitted[3]
    dry = dict(flood, graph=dfs.wrap_graph(dfs.make_undirected(dfs.romania_map["roads"]), max_flood=0))
    g4 = next(t for t in submitted if t["test_id"] == "worst_grid4x4_continuous_flood")
    corridor = next(t for t in submitted if t["test_id"] == "best_corridor_100_dry")
    items = [
        ("common_romania_dry", "BASELINE", dry, "Romania dry, Arad to Bucharest; expected optimum 418."),
        ("common_romania_flood42", "BASELINE", flood, "Original DFS flood field seed 42, Cv=60, alpha=2."),
        ("common_romania_blocked", "BASELINE", blocked, "Original flood field with Rimnicu-Pitesti blocked at 65 cm."),
        ("common_corridor100", "BEST_CASE", corridor, "Original straight 100-node corridor plus 100 dead-end spurs; exact h on main route."),
        ("common_grid4_continuous", "WORST_CASE", g4, "Original cyclic 4x4 grid with decimal flood costs, seed 7; many f thresholds."),
        ("common_same_node", "CORRECTNESS", dict(dry, goal="Arad"), "Start equals goal: count the processed root/goal once."),
        ("common_unreachable", "CORRECTNESS", {"graph": {"s": {"t": math.inf}, "t": {}}, "start": "s", "goal": "t"},
         "Only arc is blocked (+inf): all solvers must return no path."),
    ]
    return [dict(t, test_id=tid, category=cat, description=desc, algorithms=ALL, source="shared_v1")
            for tid, cat, t, desc in items]


def submitted_cases(full=False):
    out = []
    for t in dfs.get_tests(full=full):
        out.append(dict(t, test_id="dfs__" + t["test_id"], algorithms=("DFS", "IDA*", "A* (ref)"),
                        source="DFS member generator; topology/order/parameters preserved"))
    for t in ucs.build_test_cases():
        out.append(dict(t, test_id="ucs__" + t["test_id"], algorithms=("UCS", "Bi-UCS"),
                        source="UCS member generator; topology/order/parameters preserved"))
    for t in dst.get_tests(full=full):
        if not t.get("dynamic_updates"):
            out.append(dict(t, test_id="dstar__" + t["test_id"], algorithms=("A*", "D* Lite"),
                            source="A* / D* Lite member static generator; topology/order/parameters preserved"))
    return out


def select_cases(suite="all", full=False):
    return ((common_cases() if suite in ("common", "all") else []) +
            (submitted_cases(full) if suite in ("submitted", "all") else []))
