"""
DFS -> IDA*  (thanh vien: Duong Trung)  -- tuan thu BENCHMARK.md (Common Benchmark & Implementation Specification)

Giao dien chung (Section 5):
    solve(problem) -> {"path": list|None, "cost": float, "expanded": int, "extra": dict}
    - solve               : IDA*  (thuat toan cai tien duoc giao)
    - solve_ida_star      : alias cua solve
    - solve_dfs           : DFS baseline (Lec3), cung giao dien / cung dinh nghia metric
    - solve_astar_reference: A* chi de THAM CHIEU cuc bo (khong phai san pham cua minh)

`problem` co the la:
    * FloodGraphProblem / GraphProblem (OOP chuan AIMA cua co), hoac
    * dict {"graph", "start", "goal", ["locations", "C_v", "alpha"]}  (Section 12)

Dinh nghia `expanded` (Section 5.3 / 8) dung chung cho ca 3 ham:
    "mot node duoc tinh la expanded khi no duoc LAY RA khoi cau truc tim kiem dang hoat dong
     va duoc thuat toan xu ly; node dich duoc lay ra va kiem tra cung tinh."
    - DFS : pop tu stack, bo qua neu da explored (trung lap), con lai +1 (ke ca node dich).
    - A*  : pop tu heap, bo qua neu stale, con lai +1 (ke ca node dich).
    - IDA*: node duoc vao duong di hien tai (hop le: khong nam tren current path, cost huu han,
            f <= threshold) +1 (ke ca root va node dich). Node bi cat do f > threshold KHONG tinh.
Memory (Section 7): do bang tracemalloc o wrapper. `peak_frontier` chi la metric phu (extra).

Chay:  python dfs_2_idastar.py            -> self-test (Section 26)
       python dfs_2_idastar.py --bench    -> self-test + bang benchmark (ghi results.md)
       python dfs_2_idastar.py --bench --full   -> them cac test rat nang (lai 9x9, ~vai phut)
"""
import heapq, math, random, sys, time, tracemalloc
from itertools import count

INF = float("inf")

# ======================= BASELINE CUA CO (Lec3/Lec4) - KHONG SUA =======================
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
        "Urziceni": {"Vaslui": 142}
    },
    "locations": {
        "Arad": (91, 492), "Bucharest": (400, 327), "Craiova": (253, 288),
        "Drobeta": (165, 299), "Eforie": (562, 293), "Fagaras": (305, 449),
        "Giurgiu": (375, 270), "Hirsova": (534, 350), "Iasi": (473, 506),
        "Lugoj": (165, 379), "Mehadia": (168, 339), "Neamt": (406, 537),
        "Oradea": (131, 571), "Pitesti": (320, 368), "Rimnicu": (233, 410),
        "Sibiu": (207, 457), "Timisoara": (94, 410), "Urziceni": (456, 350),
        "Vaslui": (509, 444), "Zerind": (108, 531)
    }
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
        self.initial, self.goal, self.graph = initial, goal, graph
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
        self.state, self.parent, self.action, self.path_cost = state, parent, action, path_cost
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

# ======================= MO HINH NGAP LUT (ke thua / ghi de GraphProblem) =======================
def wrap_graph(undirected_graph, flood_map=None, seed=42, max_flood=55.0, decimals=1):
    """
    {u: {v: d}} -> {u: {v: {'distance': d, 'flood': f}}}.
    flood_map {(u,v): f} de truyen do ngap cu the (ap dung 2 chieu); canh con lai: f ~ U(0, max_flood).
    Do ngap la thuoc tinh cua doan duong nen u-v va v-u dung chung 1 gia tri.
    """
    rnd = random.Random(seed)
    flood_map = flood_map or {}
    wrapped = {u: {} for u in undirected_graph}
    done = set()
    for u, nbrs in undirected_graph.items():
        for v, d in nbrs.items():
            key = frozenset((u, v))
            if key in done:
                continue
            done.add(key)
            if (u, v) in flood_map:
                f = flood_map[(u, v)]
            elif (v, u) in flood_map:
                f = flood_map[(v, u)]
            else:
                f = round(rnd.uniform(0, max_flood), decimals)
            wrapped[u][v] = {"distance": d, "flood": f}
            wrapped[v][u] = {"distance": d, "flood": f}
    return wrapped

class FloodGraphProblem(GraphProblem):
    """C_v = nguong chiu ngap (cm), alpha = he so phat. `locations` (tuy chon) = toa do cho heuristic Euclid."""
    def __init__(self, initial, goal, graph, C_v=60, alpha=2, locations=None):
        super().__init__(initial, goal, graph)
        self.C_v, self.alpha, self.locations = C_v, alpha, locations

    def step_cost(self, s, a, s2):                       # OVERRIDE
        edge = self.graph[s][a]
        d, f = edge["distance"], edge["flood"]
        if f >= self.C_v:                                # rang buoc an toan cung
            return INF
        return d * (1 + self.alpha * (f / self.C_v))

# ======================= TIEN ICH DUNG CHUNG CHO CAC SOLVER =======================
def _normalize_problem(problem):
    """Nhan GraphProblem-like hoac dict {"graph","start","goal",...} (Section 12) -> GraphProblem-like."""
    if not isinstance(problem, dict):
        return problem
    g, start, goal = problem["graph"], problem["start"], problem["goal"]
    sample = next((e for nb in g.values() for e in nb.values()), None)
    if isinstance(sample, dict):                         # canh dang {'distance','flood'}
        p = FloodGraphProblem(start, goal, g, C_v=problem.get("C_v", 60), alpha=problem.get("alpha", 2))
    else:                                                # canh dang so (cost san)
        p = GraphProblem(start, goal, g)
    p.locations = problem.get("locations")
    return p

def _heuristic(problem):
    """h = Euclid chim bay toi goal. Admissible neu Euclid(u,v) <= distance(u,v) tren moi canh (cost >= distance).
    Neu problem KHONG co `locations` -> h = 0 (van dung nhung IDA* mat tinh huong dan); ten h ghi vao extra."""
    loc = getattr(problem, "locations", None)
    if loc is None:
        return (lambda s: 0.0), "zero(no locations)"
    gx, gy = loc[problem.goal]
    return (lambda s: math.hypot(loc[s][0] - gx, loc[s][1] - gy)), "euclid"

def _result(path, cost, expanded, extra):
    return {"path": path, "cost": cost, "expanded": expanded, "extra": extra}

# ======================= IDA*  (SAN PHAM CHINH) =======================
def solve_ida_star(problem):
    """
    IDA*: lap DFS gioi han theo nguong f = g + h; moi vong nang nguong len f NHO NHAT da bi cat o vong truoc.
    - Chi giu duong di hien tai (stack) + tap on_path de tranh chu trinh. KHONG co visited/explored toan cuc (Sec. 19).
    - Cai dat bang stack tuong minh (khong de quy) de khong vuong gioi han recursion cua Python.
    - Canh cost = inf (ngap >= C_v) -> f = inf -> luon bi cat -> khong bao gio di qua.
    extra: iterations, peak_frontier (= do dai duong di toi da), initial_threshold, final_threshold, heuristic.
    """
    problem = _normalize_problem(problem)
    h, h_name = _heuristic(problem)
    expanded, iterations, peak_frontier = 0, 1, 0
    root = Node(problem.initial)
    threshold = initial_threshold = h(root.state)

    def extra():
        return {"iterations": iterations, "peak_frontier": peak_frontier,
                "initial_threshold": initial_threshold, "final_threshold": threshold, "heuristic": h_name}

    while True:
        next_threshold = INF
        on_path = {root.state}
        expanded += 1                                    # root duoc xu ly o moi vong
        if problem.goal_test(root.state):
            return _result(root.solution(), root.path_cost, expanded, extra())
        stack = [(root, root.expand(problem))]           # stack = duong di hien tai
        peak_frontier = max(peak_frontier, len(stack))

        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:                            # het con -> quay lui
                on_path.discard(node.state)
                stack.pop()
                continue
            if child.state in on_path:                   # tranh chu trinh tren current path
                continue
            f = child.path_cost + h(child.state)
            if f > threshold:                            # bi cat -> chi ghi nhan de nang nguong
                next_threshold = min(next_threshold, f)
                continue
            expanded += 1                                # node hop le duoc xu ly
            if problem.goal_test(child.state):
                return _result(child.solution(), child.path_cost, expanded, extra())
            on_path.add(child.state)
            stack.append((child, child.expand(problem)))
            peak_frontier = max(peak_frontier, len(stack))

        if next_threshold == INF:                        # khong con gi de nang nguong -> vo nghiem
            return _result(None, INF, expanded, extra())
        threshold = next_threshold
        iterations += 1

solve = solve_ida_star                                   # ham `solve` ma Duc se goi

# ======================= DFS BASELINE (Lec3) cung giao dien =======================
def solve_dfs(problem):
    """
    DFS y het Lec3 (stack LIFO + explored set). Khac Lec3: bo qua con co cost = inf (khong di xuyen duong ngap;
    DFS goc khong doc step_cost nen neu giu nguyen se tra path co cost inf -> sai correctness).
    expanded: node lay ra khoi stack va khong phai ban trung lap (ke ca node dich). extra: peak_frontier = max len(stack).
    """
    problem = _normalize_problem(problem)
    expanded, peak_frontier = 0, 0
    stack = [Node(problem.initial)]
    explored = set()
    while stack:
        node = stack.pop()
        if node.state in explored:                       # ban trung lap -> khong xu ly
            continue
        expanded += 1
        if problem.goal_test(node.state):
            return _result(node.solution(), node.path_cost, expanded,
                           {"iterations": 1, "peak_frontier": peak_frontier})
        explored.add(node.state)
        stack.extend(c for c in node.expand(problem) if c.path_cost != INF)
        peak_frontier = max(peak_frontier, len(stack))
    return _result(None, INF, expanded, {"iterations": 1, "peak_frontier": peak_frontier})

# ======================= A* THAM CHIEU CUC BO =======================
def solve_astar_reference(problem):
    """A* y het Lec4, cung giao dien/cung dinh nghia expanded, chi de doi chieu trong bao cao cua minh."""
    problem = _normalize_problem(problem)
    h, _ = _heuristic(problem)
    expanded, peak_frontier = 0, 0
    start = Node(problem.initial)
    cnt = count()
    frontier = [(h(start.state), next(cnt), start)]
    best_g = {start.state: 0}
    while frontier:
        _, _, node = heapq.heappop(frontier)
        if node.path_cost > best_g.get(node.state, INF):  # stale
            continue
        expanded += 1
        if problem.goal_test(node.state):
            return _result(node.solution(), node.path_cost, expanded,
                           {"iterations": 1, "peak_frontier": peak_frontier})
        for child in node.expand(problem):
            g2 = child.path_cost
            if g2 < best_g.get(child.state, INF):
                best_g[child.state] = g2
                heapq.heappush(frontier, (g2 + h(child.state), next(cnt), child))
        peak_frontier = max(peak_frontier, len(frontier))
    return _result(None, INF, expanded, {"iterations": 1, "peak_frontier": peak_frontier})

# ======================= KIEM TRA CORRECTNESS (Section 9, 10, 26) =======================
def optimal_cost_reference(problem):
    """Dijkstra doc lap dung lam 'ground truth' cho optimality (khong dung code cua thanh vien khac)."""
    problem = _normalize_problem(problem)
    best, cnt = {problem.initial: 0}, count()
    pq = [(0, next(cnt), problem.initial)]
    while pq:
        d, _, u = heapq.heappop(pq)
        if d > best.get(u, INF):
            continue
        if problem.goal_test(u):
            return d
        for v in problem.actions(u):
            nd = d + problem.step_cost(u, v, v)
            if nd < best.get(v, INF):
                best[v] = nd
                heapq.heappush(pq, (nd, next(cnt), v))
    return INF

def verify_result(problem, result, reference_cost=None, require_optimal=False):
    """Tra ve (ok, ly_do). Kiem tra: key bat buoc, start/goal, tung canh ton tai & huu han, cost == tong cost, optimality."""
    problem = _normalize_problem(problem)
    for k in ("path", "cost", "expanded", "extra"):
        if k not in result:
            return False, f"thieu key '{k}'"
    path, cost = result["path"], result["cost"]
    if not isinstance(result["expanded"], int) or result["expanded"] < 0:
        return False, "expanded phai la so nguyen >= 0"
    if path is None:
        if cost != INF:
            return False, "path=None nhung cost != inf"
        if reference_cost is not None and reference_cost != INF:
            return False, f"tra 'khong co duong' nhung ton tai duong cost {reference_cost}"
        return True, "no-solution dung"
    if path[0] != problem.initial or path[-1] != problem.goal:
        return False, "path khong bat dau tai start / ket thuc tai goal"
    total = 0
    for a, b in zip(path, path[1:]):
        if b not in problem.graph.get(a, {}):
            return False, f"canh {a}->{b} khong ton tai"
        c = problem.step_cost(a, b, b)
        if c == INF:
            return False, f"canh {a}->{b} bi cam (ngap >= C_v)"
        total += c
    if not math.isclose(total, cost, rel_tol=1e-9, abs_tol=1e-9):
        return False, f"cost tra ve {cost} != tong cost path {total}"
    if require_optimal and reference_cost is not None and \
            not math.isclose(cost, reference_cost, rel_tol=1e-9, abs_tol=1e-9):
        return False, f"khong toi uu: {cost} vs optimal {reference_cost}"
    return True, "ok"

def heuristic_admissible_on_edges(problem):
    """Kiem tra dieu kien du cho admissible: Euclid(u,v) <= step_cost(u,v) tren moi canh huu han."""
    problem = _normalize_problem(problem)
    loc = getattr(problem, "locations", None)
    if loc is None:
        return True
    for u, nbrs in problem.graph.items():
        for v in nbrs:
            c = problem.step_cost(u, v, v)
            if c != INF and math.hypot(loc[u][0] - loc[v][0], loc[u][1] - loc[v][1]) > c + 1e-9:
                return False
    return True

# ======================= BENCHMARK WRAPPER (Section 6, 7, 21, 22) =======================
def benchmark(solver, problem, repetitions=1, single_run=False):
    """
    Do time (perf_counter, ms) va memory (tracemalloc peak, KB). Moi lan chay doc lap (solver khong giu state).
    single_run=False (mac dinh): time do KHONG bat tracemalloc (lan chay rieng) -> time khong bi tracemalloc lam cham.
    single_run=True : dung nguyen van pseudo-code Section 21 (time + memory trong CUNG 1 lan chay).
    Loi / exception -> status FAILED + reason (Section 11), khong bao gio tra 0.
    """
    try:
        if single_run:
            tracemalloc.start()
            t0 = time.perf_counter()
            res = solver(problem)
            t1 = time.perf_counter()
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            return {"status": "OK", "result": res, "time_ms": (t1 - t0) * 1000, "memory_kb": peak / 1024}
        times, res = [], None
        for _ in range(max(1, repetitions)):
            t0 = time.perf_counter()
            r = solver(problem)
            times.append((time.perf_counter() - t0) * 1000)
            res = res or r
        tracemalloc.start()
        solver(problem)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return {"status": "OK", "result": res, "time_ms": sum(times) / len(times), "memory_kb": peak / 1024}
    except Exception as e:                                # noqa: BLE001 - phai bat de danh dau FAILED
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        return {"status": "FAILED", "reason": f"exception: {e!r}"}

# ======================= BO TEST CUC BO (Section 12-17) =======================
def make_test(test_id, category, graph, start, goal, locations, description, reps=1, C_v=60, alpha=2):
    return {"test_id": test_id, "category": category, "graph": graph, "start": start, "goal": goal,
            "locations": locations, "C_v": C_v, "alpha": alpha, "description": description, "reps": reps}

def grid_graph(n, flood_fn, spacing=10.0, seed=7):
    rnd = random.Random(seed)
    G, loc = {}, {}
    for r in range(n):
        for c in range(n):
            G.setdefault((r, c), {})
            loc[(r, c)] = (r * spacing, c * spacing)
            for dr, dc in ((1, 0), (0, 1)):
                r2, c2 = r + dr, c + dc
                if r2 < n and c2 < n:
                    e = {"distance": spacing, "flood": flood_fn(rnd)}
                    G[(r, c)][(r2, c2)] = e
                    G.setdefault((r2, c2), {})[(r, c)] = e
    return G, loc

def corridor_graph(n, spacing=10.0):
    G, loc = {}, {}
    def add(u, v, d):
        e = {"distance": d, "flood": 0.0}
        G.setdefault(u, {})[v] = e
        G.setdefault(v, {})[u] = e
    for i in range(n):
        loc[("m", i)] = (i * spacing, 0.0)
        loc[("s", i)] = (i * spacing, spacing)
        add(("m", i), ("s", i), spacing)
        if i:
            add(("m", i - 1), ("m", i), spacing)
    return G, loc

def get_tests(full=False):
    loc = romania_map["locations"]
    dist = make_undirected(romania_map["roads"])
    rnd_flood = wrap_graph(dist, seed=42, max_flood=55)
    dry = wrap_graph(dist, flood_map={}, max_flood=0)
    blocked = wrap_graph(dist, flood_map={("Rimnicu", "Pitesti"): 65}, seed=42, max_flood=55)
    T = []
    T.append(make_test("baseline_romania_arad_bucharest", "BASELINE", rnd_flood, "Arad", "Bucharest", loc,
                       "Romania (teacher map), flood random seed=42 in [0,55] cm.", reps=200))
    T.append(make_test("baseline_romania_oradea_giurgiu", "BASELINE", rnd_flood, "Oradea", "Giurgiu", loc,
                       "Romania, same flood field, longer route (6 nodes).", reps=200))
    T.append(make_test("baseline_romania_iasi_craiova", "BASELINE", rnd_flood, "Iasi", "Craiova", loc,
                       "Romania, same flood field, start in the north-east corner.", reps=200))
    T.append(make_test("baseline_romania_blocked_edge", "BASELINE", blocked, "Arad", "Bucharest", loc,
                       "Romania with Rimnicu-Pitesti flooded at 65 cm >= C_v: edge forbidden, route must detour via Fagaras.", reps=200))
    T.append(make_test("best_romania_adjacent_dry", "BEST_CASE", dry, "Sibiu", "Fagaras", loc,
                       "Start and goal adjacent, all roads dry (flood=0): cost = distance, Euclid h is almost exact -> shallow search.", reps=200))
    G, L = corridor_graph(100)
    T.append(make_test("best_corridor_100_dry", "BEST_CASE", G, ("m", 0), ("m", 99), L,
                       "Straight 100-node corridor, flood=0, one dead-end spur per node: Euclid h equals the true remaining cost, "
                       "so the first threshold already contains the optimal path.", reps=20))
    sizes = (4, 5, 6, 7) + ((8,) if full else ())
    for n in sizes:
        G, L = grid_graph(n, lambda r: round(r.uniform(0, 55), 1))
        T.append(make_test(f"worst_grid{n}x{n}_continuous_flood", "WORST_CASE", G, (0, 0), (n - 1, n - 1), L,
                           f"{n}x{n} street grid (cycles), continuous decimal flood: Euclid (diagonal) underestimates Manhattan cost, "
                           "many near-equal detours, almost every f-value distinct -> threshold rises in tiny steps."))
    # STRESS: cung topology luoi, doi do hat cua flood va quy mo (n=8 quantized chi o --full vi cham)
    for n, lab in [(6, "dry"), (6, "quantized"), (7, "dry"), (7, "quantized"), (8, "dry"), (9, "dry"), (10, "dry")] + \
                  ([(8, "quantized")] if full else []):
        ffn = (lambda r: 0.0) if lab == "dry" else (lambda r: r.choice([0, 15, 30, 45]))
        G, L = grid_graph(n, ffn)
        T.append(make_test(f"stress_grid{n}x{n}_{lab}_flood", "STRESS", G, (0, 0), (n - 1, n - 1), L,
                           f"{n}x{n} street grid, flood {'=0' if lab == 'dry' else 'in {0,15,30,45} cm'}: same topology as the "
                           "continuous-flood test, used to isolate flood granularity and graph size."))
    return T

def problem_from_test(t):
    return FloodGraphProblem(t["start"], t["goal"], t["graph"], C_v=t["C_v"], alpha=t["alpha"], locations=t["locations"])

# ======================= SELF-TEST (Section 26) =======================
def self_test():
    loc = romania_map["locations"]
    dist = make_undirected(romania_map["roads"])
    dry = wrap_graph(dist, flood_map={}, max_flood=0)
    rnd = wrap_graph(dist, seed=42, max_flood=55)
    block_goal = wrap_graph(dist, flood_map={("Bucharest", v): 65 for v in dist["Bucharest"]}, seed=42, max_flood=55)
    cases = [
        ("dry Arad->Bucharest (known optimum 418)", FloodGraphProblem("Arad", "Bucharest", dry, locations=loc), 418),
        ("random flood Arad->Bucharest", FloodGraphProblem("Arad", "Bucharest", rnd, locations=loc), None),
        ("blocked Rimnicu-Pitesti", FloodGraphProblem("Arad", "Bucharest", wrap_graph(dist, flood_map={("Rimnicu", "Pitesti"): 65}, seed=42, max_flood=55), locations=loc), None),
        ("start == goal", FloodGraphProblem("Arad", "Arad", rnd, locations=loc), 0),
        ("unreachable goal (all Bucharest roads flooded)", FloodGraphProblem("Arad", "Bucharest", block_goal, locations=loc), INF),
        ("dict input (Section 12) Oradea->Giurgiu", {"graph": rnd, "start": "Oradea", "goal": "Giurgiu", "locations": loc}, None),
    ]
    all_ok = True
    for name, prob, known in cases:
        ref = optimal_cost_reference(prob)
        if known is not None:
            assert math.isclose(ref, known) or (ref == known == INF), f"oracle {ref} != known {known}"
        for solver, need_opt in ((solve, True), (solve_dfs, False), (solve_astar_reference, True)):
            r = solver(prob)
            ok, why = verify_result(prob, r, reference_cost=ref, require_optimal=need_opt)
            all_ok &= ok
            print(f"[{'PASS' if ok else 'FAIL'}] {name:<48} {solver.__name__:<22} cost={r['cost'] if r['cost']==INF else round(r['cost'],2)} "
                  f"expanded={r['expanded']} extra={ {k: (round(v,2) if isinstance(v,float) else v) for k,v in r['extra'].items()} } {'' if ok else '-> '+why}")
    adm = heuristic_admissible_on_edges(FloodGraphProblem("Arad", "Bucharest", rnd, locations=loc))
    print(f"[{'PASS' if adm else 'FAIL'}] heuristic Euclid <= step_cost tren moi canh Romania (admissible)")
    all_ok &= adm
    print("SELF-TEST:", "PASS" if all_ok else "FAIL")
    return all_ok

# ======================= BANG BENCHMARK (Section 23) =======================
def fmt(c):
    return "inf" if c == INF else f"{c:.2f}"

def run_benchmark(full=False, out_path="results.md"):
    lines = []
    def out(s=""):
        print(s, flush=True); lines.append(s)
    out("| Test | Category | Algorithm | Status | Cost | Expanded | Iterations | Peak frontier | Time (ms) | Memory (KB) |")
    out("|---|---|---|---|---|---|---|---|---|---|")
    notes = []
    for t in get_tests(full):
        prob = problem_from_test(t)
        ref = optimal_cost_reference(prob)
        for name, solver, need_opt in (("DFS", solve_dfs, False), ("IDA*", solve, True), ("A* (ref)", solve_astar_reference, True)):
            b = benchmark(solver, prob, t["reps"])
            if b["status"] == "OK":
                ok, why = verify_result(prob, b["result"], reference_cost=ref, require_optimal=need_opt)
                if not ok:
                    b = {"status": "FAILED", "reason": why}
            if b["status"] != "OK":
                out(f"| {t['test_id']} | {t['category']} | {name} | FAILED | - | - | - | - | - | - |")
                notes.append(f"FAILED {t['test_id']} {name}: {b['reason']}")
                continue
            r = b["result"]; x = r["extra"]
            out(f"| {t['test_id']} | {t['category']} | {name} | PASS | {fmt(r['cost'])} | {r['expanded']} | {x['iterations']} | "
                f"{x['peak_frontier']} | {b['time_ms']:.3f} | {b['memory_kb']:.1f} |")
    if notes:
        out(); [out("- " + n) for n in notes]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    ok = self_test()
    if "--bench" in sys.argv:
        print()
        run_benchmark(full="--full" in sys.argv)
    sys.exit(0 if ok else 1)
