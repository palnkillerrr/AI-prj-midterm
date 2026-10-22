# -*- coding: utf-8 -*-
"""
AI Midterm Project - Cap thuat toan UCS -> Bidirectional UCS (thanh vien: Mint)
Tuan theo BENCHMARK_SPEC.md (Common Benchmark & Implementation Specification).

Cach chay:
    python ucs_biucs_benchmark.py              # self-test (Section 26) + benchmark (Section 23) + xuat CSV/JSON
    python ucs_biucs_benchmark.py --selftest   # chi chay self-test
    python ucs_biucs_benchmark.py --diag       # them bang chan doan (time khong tracemalloc, do thi dao dung san)

Goi tu script benchmark chung cua Duc:
    from ucs_biucs_benchmark import solve_ucs, solve_biucs   # hoac: solve (= solve_biucs)
    result = solve_biucs({"graph": graph, "start": s, "goal": t})
    # result = {"path": [...], "cost": ..., "expanded": ..., "extra": {...}}

Quy uoc chung (giong nhau cho UCS va Bi-UCS):
  * graph: dict dang {u: {v: cost}}; do thi co huong hay vo huong deu duoc
    (do thi vo huong = moi canh co ca 2 chieu, nhu make_undirected cua co).
  * expanded: +1 moi khi mot node duoc heappop khoi hang doi VA duoc xu ly
    (entry cu da loi thoi bi bo qua thi khong tinh). Node goal duoc pop ra de
    kiem tra thi co tinh. Bi-UCS: expanded = expanded_forward + expanded_backward.
  * Hoa chi phi (tie-break): theo thu tu day vao heap (FIFO), giong code cua co.
  * Ca hai thuat toan dung CHUNG GraphProblem/Node cua co -> thoi gian so sanh duoc.
"""
import gc
import heapq
import json
import csv
import math
import random
import statistics
import sys
import time
import tracemalloc
from itertools import count

try:  # tranh loi in tieng Viet tren console Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

INF = float("inf")

# =============================================================================
# 1. BASELINE CUA CO (Lec3/Lec4) - giu nguyen
# =============================================================================
romania_map = {
    "roads": {
        "Arad": {"Zerind": 75, "Sibiu": 140, "Timisoara": 118},
        "Bucharest": {"Urziceni": 85, "Pitesti": 101, "Giurgiu": 90, "Fagaras": 211},
        "Craiova": {"Drobeta": 120, "Rimnicu": 146, "Pitesti": 138},
        "Drobeta": {"Mehadia": 75},
        "Eforie": {"Hirsova": 86},
        "Fagaras": {"Sibiu": 99},
        "Hirsova": {"Urziceni": 98},
        "Iasi": {"Vaslui": 92, "Neamt": 87},
        "Lugoj": {"Timisoara": 111, "Mehadia": 70},
        "Oradea": {"Zerind": 71, "Sibiu": 151},
        "Pitesti": {"Rimnicu": 97},
        "Rimnicu": {"Sibiu": 80},
        "Urziceni": {"Vaslui": 142},
    },
    "locations": {
        "Arad": (91, 492), "Bucharest": (400, 327), "Craiova": (253, 288),
        "Drobeta": (165, 299), "Eforie": (562, 293), "Fagaras": (305, 449),
        "Giurgiu": (375, 270), "Hirsova": (534, 350), "Iasi": (473, 506),
        "Lugoj": (165, 379), "Mehadia": (168, 339), "Neamt": (406, 537),
        "Oradea": (131, 571), "Pitesti": (320, 368), "Rimnicu": (233, 410),
        "Sibiu": (207, 457), "Timisoara": (94, 410), "Urziceni": (456, 350),
        "Vaslui": (509, 444), "Zerind": (108, 531),
    },
}


def make_undirected(roads):
    G = {}
    for u, nbrs in roads.items():
        G.setdefault(u, {})
        for v, w in nbrs.items():
            G[u][v] = w
            G.setdefault(v, {})
            G[v].setdefault(u, w)
    return G


class GraphProblem:
    def __init__(self, initial, goal, graph):
        self.initial = initial
        self.goal = goal
        self.graph = graph

    def actions(self, state):
        return list(self.graph.get(state, {}).keys())

    def result(self, state, action):
        return action

    def goal_test(self, state):
        return state == self.goal

    def step_cost(self, s, a, s2):
        return self.graph[s][a]


class Node:
    def __init__(self, state, parent=None, action=None, path_cost=0):
        self.state = state
        self.parent = parent
        self.action = action
        self.path_cost = path_cost

    def expand(self, problem):
        s = self.state
        for a in problem.actions(s):
            s2 = problem.result(s, a)
            yield Node(s2, self, a, self.path_cost + problem.step_cost(s, a, s2))

    def solution(self):
        path, n = [], self
        while n:
            path.append(n.state)
            n = n.parent
        return list(reversed(path))


# =============================================================================
# 2. UCS (baseline) - logic GIU NGUYEN nhu uniform_cost_search cua co,
#    chi them bo dem expanded + peak_frontier (auxiliary, KHONG phai memory).
# =============================================================================
def uniform_cost_search(problem, stats):
    start = Node(problem.initial)
    counter = count()
    frontier = []
    heapq.heappush(frontier, (0, next(counter), start))
    stats["peak_frontier"] = 1
    explored_cost = {start.state: 0}

    while frontier:
        cost, _, node = heapq.heappop(frontier)
        if cost > explored_cost.get(node.state, INF):
            continue                        # entry cu, khong xu ly -> khong tinh expanded
        stats["expanded"] += 1              # node duoc lay ra va xu ly

        if problem.goal_test(node.state):
            return node

        for child in node.expand(problem):
            g_new = child.path_cost
            if g_new < explored_cost.get(child.state, INF):
                explored_cost[child.state] = g_new
                heapq.heappush(frontier, (g_new, next(counter), child))
        if len(frontier) > stats["peak_frontier"]:
            stats["peak_frontier"] = len(frontier)
    return None


def solve_ucs(problem):
    """Common Solver Interface (Section 5) cho UCS."""
    graph, start, goal = problem["graph"], problem["start"], problem["goal"]
    stats = {"expanded": 0, "peak_frontier": 0}
    node = uniform_cost_search(GraphProblem(start, goal, graph), stats)
    extra = {"peak_frontier": stats["peak_frontier"]}
    if node is None:
        return {"path": None, "cost": INF, "expanded": stats["expanded"], "extra": extra}
    return {"path": node.solution(), "cost": node.path_cost, "expanded": stats["expanded"], "extra": extra}


# =============================================================================
# 3. BIDIRECTIONAL UCS (thuat toan cai tien)
#    - forward: UCS tu start tren graph
#    - backward: UCS tu goal tren DO THI DAO (dung voi ca do thi co huong)
#    - luan phien mo rong phia co g nho hon o dinh hang doi
#    - mu = min gF(v) + gB(v) tren moi nut v ca hai phia da cham toi
#    - DUNG khi topF + topB >= mu  (khong dung ngay khi hai phia cham nhau)
# =============================================================================
def reverse_graph(graph):
    """Dao chieu moi canh u->v thanh v->u (giu nguyen chi phi)."""
    rev = {u: {} for u in graph}
    for u, nbrs in graph.items():
        for v, w in nbrs.items():
            rev.setdefault(v, {})[u] = w
    return rev


def bidirectional_ucs(graph, start, goal, stats, rgraph=None):
    """Tra ve (path, cost). Dung chung GraphProblem/Node voi UCS cua co.
    rgraph: do thi dao da dung san (tuy chon). Neu None thi dung trong ham va tinh vao time/memory."""
    if start == goal:
        # Process a singleton active heap so the root/goal counts once, as in UCS.
        singleton = [(0, 0, Node(start))]
        heapq.heappop(singleton)
        stats["expanded_forward"] = 1
        stats["peak_frontier"] = 1
        return [start], 0

    fwd = GraphProblem(start, goal, graph)
    if rgraph is None:
        rgraph = reverse_graph(graph)       # O(V+E): chi phi that cua Bi-UCS khi graph chi luu canh ra
    bwd = GraphProblem(goal, start, rgraph)

    counter = count()
    root_f, root_b = Node(start), Node(goal)
    open_f, open_b = [(0, next(counter), root_f)], [(0, next(counter), root_b)]
    stats["peak_frontier"] = 2
    g_f, g_b = {start: 0}, {goal: 0}
    best_f, best_b = {start: root_f}, {goal: root_b}
    mu, meet = INF, None

    while open_f and open_b:
        # bo cac entry cu (lazy deletion) - khong tinh expanded
        while open_f and open_f[0][0] > g_f[open_f[0][2].state]:
            heapq.heappop(open_f)
        while open_b and open_b[0][0] > g_b[open_b[0][2].state]:
            heapq.heappop(open_b)
        if not open_f or not open_b:
            break

        # DIEU KIEN DUNG dam bao toi uu: moi duong chua thay deu co chi phi >= topF + topB
        if open_f[0][0] + open_b[0][0] >= mu:
            break

        if open_f[0][0] <= open_b[0][0]:
            heap, g_this, best_this, g_other, prob, key = open_f, g_f, best_f, g_b, fwd, "expanded_forward"
        else:
            heap, g_this, best_this, g_other, prob, key = open_b, g_b, best_b, g_f, bwd, "expanded_backward"

        _, _, node = heapq.heappop(heap)
        stats[key] += 1                     # node duoc lay ra va xu ly

        for child in node.expand(prob):
            if not math.isfinite(child.path_cost):
                continue                    # blocked edges must not enter either wave
            s = child.state
            if child.path_cost < g_this.get(s, INF):
                g_this[s] = child.path_cost
                best_this[s] = child
                heapq.heappush(heap, (child.path_cost, next(counter), child))
            if s in g_other:                # hai phia cung cham toi s -> cap nhat mu
                cand = g_this[s] + g_other[s]
                if cand < mu:
                    mu, meet = cand, s
        if len(open_f) + len(open_b) > stats["peak_frontier"]:
            stats["peak_frontier"] = len(open_f) + len(open_b)

    if meet is None:
        return None, INF
    stats["meeting_node"] = meet
    left = best_f[meet].solution()                  # start ... meet
    right = best_b[meet].solution()                 # goal ... meet (tren do thi dao)
    return left + right[::-1][1:], mu               # start ... meet ... goal


def solve_biucs(problem):
    """Common Solver Interface (Section 5) cho Bidirectional UCS."""
    stats = {"expanded_forward": 0, "expanded_backward": 0, "peak_frontier": 0, "meeting_node": None}
    path, cost = bidirectional_ucs(problem["graph"], problem["start"], problem["goal"], stats,
                                   problem.get("reverse_graph"))   # khoa tuy chon, khong bat buoc
    expanded = stats["expanded_forward"] + stats["expanded_backward"]
    return {"path": path, "cost": cost, "expanded": expanded, "extra": stats}


solve = solve_biucs          # thuat toan duoc giao (de script chung cua Duc goi)
SOLVERS = {"UCS": solve_ucs, "Bi-UCS": solve_biucs}


# =============================================================================
# 4. CORRECTNESS (Section 9, 10, 11)
# =============================================================================
def validate(result, problem, baseline_cost=None):
    """Tra ve (ok, reason). baseline_cost = cost cua UCS de kiem tra optimality."""
    graph, start, goal = problem["graph"], problem["start"], problem["goal"]
    for k in ("path", "cost", "expanded", "extra"):
        if k not in result:
            return False, f"missing key '{k}'"
    path, cost, expanded = result["path"], result["cost"], result["expanded"]
    if not isinstance(expanded, int) or expanded < 0:
        return False, "expanded must be an int >= 0"
    if not isinstance(result["extra"], dict):
        return False, "extra must be a dict"

    if path is None:
        if cost != INF:
            return False, "path is None but cost is not inf"
        if baseline_cost is not None and baseline_cost != INF:
            return False, "no path returned but baseline found one"
        return True, "no path (consistent with baseline)"

    if not path or path[0] != start:
        return False, "path does not start at start"
    if path[-1] != goal:
        return False, "path does not end at goal"
    total = 0
    for a, b in zip(path, path[1:]):
        if b not in graph.get(a, {}):
            return False, f"edge {a!r}->{b!r} not in graph"
        total += graph[a][b]
    if not math.isclose(total, cost, rel_tol=1e-9, abs_tol=1e-9):
        return False, f"cost {cost} != path cost {total}"
    if baseline_cost is not None and not math.isclose(cost, baseline_cost, rel_tol=1e-9, abs_tol=1e-9):
        return False, f"not optimal: cost {cost} != baseline {baseline_cost}"
    return True, "ok"


# =============================================================================
# 5. BENCHMARK WRAPPER (Section 21, 22) - do time + memory, giong nhau cho moi solver
# =============================================================================
def benchmark(solver, problem, repetitions=5, baseline_cost=None):
    times, mems, first = [], [], None
    try:
        for _ in range(repetitions):
            gc.collect()                                    # moi lan chay doc lap
            tracemalloc.start()
            t0 = time.perf_counter()
            result = solver(problem)
            t1 = time.perf_counter()
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            times.append((t1 - t0) * 1000)
            mems.append(peak / 1024)
            if first is None:
                first = result
            elif result["cost"] != first["cost"] or result["expanded"] != first["expanded"]:
                return {"status": "FAILED", "reason": "non-deterministic result between repetitions"}
    except Exception as e:                                  # crash -> FAILED, khong bo qua
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        return {"status": "FAILED", "reason": f"crash: {e!r}"}

    ok, reason = validate(first, problem, baseline_cost)
    row = {
        "status": "PASS" if ok else "FAILED",
        "reason": reason,
        "cost": first["cost"],
        "expanded": first["expanded"],
        "time_ms": statistics.median(times),               # trung vi cua cac lan lap
        "time_ms_min": min(times),
        "memory_kb": statistics.median(mems),              # tracemalloc peak (KB)
        "path_len": None if first["path"] is None else len(first["path"]) - 1,
        "extra": first["extra"],
    }
    return row


# =============================================================================
# 6. TEST CASES (Section 12-16). Ten category mo ta DAC DIEM INPUT, khong phai ket qua do.
# =============================================================================
def grid_graph(rows, cols, cost_fn=lambda cell: 1, walls=()):
    """Luoi 4 huong. Chi phi di VAO o v = cost_fn(v) -> do thi co huong neu cost khac nhau."""
    walls = set(walls)
    g = {}
    for r in range(rows):
        for c in range(cols):
            if (r, c) in walls:
                continue
            nb = {}
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                v = (r + dr, c + dc)
                if 0 <= v[0] < rows and 0 <= v[1] < cols and v not in walls:
                    nb[v] = cost_fn(v)
            g[(r, c)] = nb
    return g


def random_connected_graph(n, extra_edges_per_node, seed, wmax=20):
    rnd = random.Random(seed)
    g = {i: {} for i in range(n)}

    def add(u, v, w):
        if u != v:
            g[u][v] = w
            g[v][u] = w
    for i in range(1, n):                      # cay khung -> chac chan lien thong
        add(i, rnd.randrange(i), rnd.randint(1, wmax))
    for _ in range(extra_edges_per_node * n):
        add(rnd.randrange(n), rnd.randrange(n), rnd.randint(1, wmax))
    return g


def chain_graph(n):
    g = {i: {} for i in range(n)}
    for i in range(n - 1):
        g[i][i + 1] = 1
        g[i + 1][i] = 1
    return g


def hub_graph(chain_len, leaves):
    """Co huong: start -> chuoi -> hub -> goal; hub co rat nhieu nut di vao (leaf -> hub)."""
    g = {("c", i): {("c", i + 1): 1} for i in range(chain_len)}
    hub = ("c", chain_len)
    g[hub] = {"goal": 1}
    g["goal"] = {}
    for k in range(leaves):
        g[("leaf", k)] = {hub: 1}
    return g


def build_test_cases():
    tests = []

    def add(test_id, category, graph, start, goal, edge_costs, description):
        tests.append({"test_id": test_id, "category": category, "graph": graph, "start": start,
                      "goal": goal, "edge_costs": edge_costs, "description": description})

    romania = make_undirected(romania_map["roads"])
    add("baseline_01", "BASELINE", romania, "Arad", "Bucharest", "road distance (teacher map)",
        "Teacher Romania map (Lec3/Lec4), undirected, same start/goal as the other pairs.")

    rnd = random.Random(7)
    add("best_01", "BEST_CASE", grid_graph(31, 31), (15, 10), (15, 20), "1 per move",
        "Open 31x31 grid, no obstacles, start/goal 10 steps apart in the middle: both directions branch "
        "equally, the two searches meet halfway, two radius-5 waves instead of one radius-10 wave.")
    add("best_02", "BEST_CASE", random_connected_graph(3000, 3, seed=2), 0, 2999, "random 1..20",
        "Random connected graph, 3000 nodes, average degree ~8: large branching factor at both ends, "
        "so nodes within radius r grow fast with r and two half-radius balls are much smaller.")

    add("worst_01", "WORST_CASE", chain_graph(2000), 0, 1999, "1 per edge",
        "Chain graph (branching factor 1): forward + backward together cover exactly the same nodes as "
        "UCS, so bidirectional search has no advantage, only extra bookkeeping.")
    add("worst_02", "WORST_CASE", hub_graph(50, 3000), ("c", 0), "goal", "1 per edge",
        "Directed graph: start -> 50-node chain -> hub -> goal, and 3000 leaves point into the hub. "
        "Forward branching is 1 but backward branching (in-degree) is 3000, so the backward search explodes.")
    walls = {(0, 2), (1, 2), (3, 2)}
    mud = {(2, 3): 5, (2, 4): 5}
    add("worst_03", "WORST_CASE", grid_graph(4, 6, lambda v: mud.get(v, 1), walls), (1, 0), (2, 5),
        "cost of the entered cell: 1, mud = 5 (directed)",
        "Team's 6x4 map (wall with one gap, two mud cells after the gap): tiny graph with a bottleneck, "
        "both waves already cover almost the whole map before the stop condition holds.")

    stress_cost = {}
    for r in range(150):
        for c in range(150):
            stress_cost[(r, c)] = rnd.randint(1, 9)
    add("stress_01", "STRESS", grid_graph(150, 150, lambda v: stress_cost[v]), (0, 0), (149, 149),
        "cost of the entered cell: random 1..9 (seed 7, directed)",
        "Large weighted grid, 22,500 nodes, corner to corner: start and goal far apart on a 2D map.")
    add("stress_02", "STRESS", random_connected_graph(20000, 3, seed=11), 0, 19999, "random 1..20",
        "Large random graph, 20,000 nodes, average degree ~8.")
    return tests


REPETITIONS = {"BASELINE": 50, "BEST_CASE": 10, "WORST_CASE": 10, "STRESS": 3}


# =============================================================================
# 7. SELF-TEST (Section 26)
# =============================================================================
def dijkstra_reference(graph, start, goal):
    """Cai dat doc lap (khong dung GraphProblem/Node) de doi chieu cost."""
    dist = {start: 0}
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == goal:
            return d
        if d > dist[u]:
            continue
        for v, w in graph.get(u, {}).items():
            if d + w < dist.get(v, INF):
                dist[v] = d + w
                heapq.heappush(pq, (d + w, v))
    return INF


def self_test(verbose=True):
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))
        if verbose:
            print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    romania = make_undirected(romania_map["roads"])
    p = {"graph": romania, "start": "Arad", "goal": "Bucharest"}
    ru, rb = solve_ucs(p), solve_biucs(p)
    if verbose:
        print("  UCS   :", ru)
        print("  Bi-UCS:", rb)
    check("Romania UCS: cost 418, same path as teacher notebook",
          ru["cost"] == 418 and ru["path"] == ["Arad", "Sibiu", "Rimnicu", "Pitesti", "Bucharest"])
    check("Romania UCS: expanded == 13 (= 13 'Expanded' lines in teacher notebook)", ru["expanded"] == 13)
    check("Romania Bi-UCS: valid path, cost == UCS (optimal)", validate(rb, p, ru["cost"])[0])
    check("Romania Bi-UCS: expanded == forward + backward",
          rb["expanded"] == rb["extra"]["expanded_forward"] + rb["extra"]["expanded_backward"])

    p0 = {"graph": romania, "start": "Arad", "goal": "Arad"}
    check("start == goal -> path [start], cost 0 (both)",
          solve_ucs(p0)["path"] == ["Arad"] and solve_biucs(p0)["path"] == ["Arad"] and solve_biucs(p0)["cost"] == 0)

    iso = dict(romania)
    iso["Atlantis"] = {}
    p1 = {"graph": iso, "start": "Arad", "goal": "Atlantis"}
    check("unreachable goal -> path None, cost inf (both)",
          solve_ucs(p1)["path"] is None and solve_biucs(p1)["path"] is None and solve_biucs(p1)["cost"] == INF)

    dg = {"a": {"b": 1, "c": 5}, "b": {"c": 1}, "c": {"a": 1}}
    check("directed graph a->c: cost 2 via b (reverse edges built correctly)",
          solve_biucs({"graph": dg, "start": "a", "goal": "c"})["cost"] == 2)
    check("directed graph c->a: cost 1",
          solve_biucs({"graph": dg, "start": "c", "goal": "a"})["cost"] == 1)

    rnd = random.Random(2026)
    bad, nopath, n_tests = 0, 0, 1000
    for _ in range(n_tests):
        n = rnd.randint(2, 40)
        directed = rnd.random() < 0.5
        g = {i: {} for i in range(n)}
        for _ in range(rnd.randint(n // 2, 3 * n)):
            u, v, w = rnd.randrange(n), rnd.randrange(n), rnd.randint(1, 12)
            if u != v:
                g[u][v] = w
                if not directed:
                    g[v][u] = w
        s, t = rnd.sample(range(n), 2)
        prob = {"graph": g, "start": s, "goal": t}
        ref = dijkstra_reference(g, s, t)
        nopath += ref == INF
        r_u, r_b = solve_ucs(prob), solve_biucs(prob)
        if not (validate(r_u, prob, ref)[0] and validate(r_b, prob, ref)[0]):
            bad += 1
    check(f"{n_tests} random graphs (directed + undirected, {nopath} without path): "
          f"UCS and Bi-UCS valid and optimal vs independent Dijkstra ({bad} failures)", bad == 0)

    ok = all(c for _, c in checks)
    print(f"SELF-TEST: {'PASS' if ok else 'FAIL'} ({sum(c for _, c in checks)}/{len(checks)})")
    return ok


# =============================================================================
# 8. CHAY BENCHMARK + XUAT BANG (Section 23)
# =============================================================================
def fmt(x, nd=3):
    if x is None:
        return "-"
    if isinstance(x, float):
        return "inf" if x == INF else f"{x:.{nd}f}"
    return str(x)


def run_benchmark(tests=None, out_prefix="benchmark_ucs_biucs"):
    tests = tests or build_test_cases()
    rows = []
    for tc in tests:
        problem = {"graph": tc["graph"], "start": tc["start"], "goal": tc["goal"]}
        reps = REPETITIONS.get(tc["category"], 5)
        r_ucs = benchmark(solve_ucs, problem, reps)                            # baseline truoc
        base_cost = r_ucs.get("cost") if r_ucs["status"] == "PASS" else None
        r_bi = benchmark(solve_biucs, problem, reps, baseline_cost=base_cost)  # kiem tra optimality vs UCS
        if r_ucs["status"] != "PASS":
            r_bi = dict(r_bi, status="FAILED", reason="baseline UCS failed, optimality cannot be verified")
        for alg, r in (("UCS", r_ucs), ("Bi-UCS", r_bi)):
            ex = r.get("extra", {}) or {}
            rows.append({
                "test_id": tc["test_id"], "category": tc["category"], "algorithm": alg,
                "status": r["status"], "reason": r.get("reason", ""),
                "cost": r.get("cost"), "expanded": r.get("expanded"),
                "time_ms": r.get("time_ms"), "time_ms_min": r.get("time_ms_min"), "memory_kb": r.get("memory_kb"),
                "expanded_forward": ex.get("expanded_forward"), "expanded_backward": ex.get("expanded_backward"),
                "peak_frontier": ex.get("peak_frontier"), "path_len": r.get("path_len"),
                "repetitions": reps, "description": tc["description"],
            })

    print("\n| Test | Category | Algorithm | Status | Cost | Expanded | Time (ms) | Memory (KB) "
          "| Expanded F | Expanded B | Peak Frontier |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['test_id']} | {r['category']} | {r['algorithm']} | {r['status']} | {fmt(r['cost'], 0)} "
              f"| {fmt(r['expanded'])} | {fmt(r['time_ms'])} | {fmt(r['memory_kb'], 1)} "
              f"| {fmt(r['expanded_forward'])} | {fmt(r['expanded_backward'])} | {fmt(r['peak_frontier'])} |")

    print("\nTi le Bi-UCS / UCS (< 1 la Bi-UCS tot hon):")
    print("| Test | Category | Expanded | Time | Memory | Peak Frontier |")
    print("|---|---|---|---|---|---|")
    by = {}
    for r in rows:
        by.setdefault(r["test_id"], {})[r["algorithm"]] = r
    for tid, d in by.items():
        u, b = d["UCS"], d["Bi-UCS"]
        if u["status"] != "PASS" or b["status"] != "PASS":
            print(f"| {tid} | {u['category']} | FAILED | - | - | - |")
            continue
        q = lambda k: f"{b[k] / u[k]:.2f}x" if u[k] else "-"
        print(f"| {tid} | {u['category']} | {q('expanded')} | {q('time_ms')} | {q('memory_kb')} | {q('peak_frontier')} |")

    failed = [r for r in rows if r["status"] != "PASS"]
    for r in failed:
        print(f"FAILED: {r['test_id']} {r['algorithm']}: {r['reason']}")

    with open(out_prefix + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("inf" if v == INF else v) for k, v in r.items()})
    with open(out_prefix + ".json", "w", encoding="utf-8") as f:
        json.dump([{k: ("inf" if v == INF else v) for k, v in r.items()} for r in rows], f, indent=1, default=str)
    print(f"\nDa luu: {out_prefix}.csv, {out_prefix}.json")
    return rows


def diagnostics(tests=None):
    """KHONG thay benchmark chinh. Tach 2 yeu to anh huong toi time/memory cua Bi-UCS:
    (a) tracemalloc lam cham ham cap phat nhieu -> do them time KHONG bat tracemalloc;
    (b) dung do thi dao ben trong solve -> do them ban Bi-UCS nhan do thi dao dung san."""
    tests = tests or build_test_cases()

    def time_only(fn, problem, reps):
        ts = []
        for _ in range(reps):
            gc.collect()
            t0 = time.perf_counter(); fn(problem); ts.append((time.perf_counter() - t0) * 1000)
        return statistics.median(ts)

    def mem_only(fn, problem):
        gc.collect(); tracemalloc.start(); fn(problem)
        peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
        return peak / 1024

    print("\n| Test | UCS time no-TM (ms) | Bi-UCS time no-TM (ms) | Bi-UCS* time no-TM (ms) | UCS mem (KB) | Bi-UCS* mem (KB) | Bi/UCS time | Bi*/UCS time | Bi*/UCS mem |")
    print("|---|---|---|---|---|---|---|---|---|")
    out = []
    for tc in tests:
        p = {"graph": tc["graph"], "start": tc["start"], "goal": tc["goal"]}
        p_star = dict(p, reverse_graph=reverse_graph(tc["graph"]))   # dung san, ngoai phep do
        reps = REPETITIONS.get(tc["category"], 5)
        tu, tb, tbs = time_only(solve_ucs, p, reps), time_only(solve_biucs, p, reps), time_only(solve_biucs, p_star, reps)
        mu_, mbs = mem_only(solve_ucs, p), mem_only(solve_biucs, p_star)
        assert solve_biucs(p_star)["cost"] == solve_ucs(p)["cost"]
        print(f"| {tc['test_id']} | {tu:.3f} | {tb:.3f} | {tbs:.3f} | {mu_:.1f} | {mbs:.1f} | {tb/tu:.2f}x | {tbs/tu:.2f}x | {mbs/mu_:.2f}x |")
        out.append(dict(test_id=tc["test_id"], ucs_ms=tu, bi_ms=tb, bi_star_ms=tbs, ucs_kb=mu_, bi_star_kb=mbs))
    print("Bi-UCS* = Bi-UCS nhan san do thi dao (problem['reverse_graph']); no-TM = khong bat tracemalloc.")
    return out


if __name__ == "__main__":
    print("=== SELF-TEST (Section 26) ===")
    ok = self_test()
    if not ok:
        sys.exit(1)
    if "--selftest" not in sys.argv:
        print("\n=== BENCHMARK (Section 23) ===")
        run_benchmark()
    if "--diag" in sys.argv:
        print("\n=== CHAN DOAN (khong thuoc benchmark chinh) ===")
        diagnostics()
