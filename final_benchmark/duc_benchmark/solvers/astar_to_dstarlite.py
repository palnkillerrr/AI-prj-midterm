"""
A* -> D* Lite  (thanh vien: Phuong Anh)  -- tuan thu BENCHMARK.md (Common Benchmark & Implementation Specification)

Giao dien chung (Section 5):
    solve(problem) -> {"path": list|None, "cost": float, "expanded": int, "extra": dict}
    - solve                  : D* Lite (thuat toan cai tien duoc giao - ban day du Koenig & Likhachev 2002)
    - solve_d_star_lite      : alias cua solve
    - solve_astar            : A* baseline (Lec4), cung giao dien / cung dinh nghia metric
    - DStarLitePlanner       : class D* Lite day du (co k_m, g, rhs, U, update_vertex, compute_shortest_path)

`problem` co the la:
    * FloodGraphProblem / GraphProblem (OOP chuan AIMA cua co), hoac
    * dict {"graph", "start", "goal", ["locations", "C_v", "alpha", "dynamic_updates"]}  (Section 12)

Dinh nghia `expanded` (Section 5.3 / 8) dung chung cho ca 2 ham:
    "mot node duoc tinh la expanded khi no duoc LAY RA khoi cau truc tim kiem dang hoat dong
     va duoc thuat toan xu ly; node dich/start duoc lay ra va xu ly cung tinh."
    - A*     : pop tu heap, bo qua neu stale (g > best_g), con lai +1 (ke ca node dich).
    - D* Lite: pop tu priority queue U, bo qua ban stale (lazy deletion) va lan chi cap nhat key
               (k_old < k_new); moi lan dinh thuc su duoc xu ly trang thai (g > rhs hoac g < rhs) +1.
Memory (Section 7): do bang tracemalloc o wrapper. `peak_frontier` chi la metric phu (extra).

Chay:  python astar_2_dstarlite.py              -> self-test (Section 26)
       python astar_2_dstarlite.py --bench      -> self-test + bang benchmark (ghi results.md)
       python astar_2_dstarlite.py --bench --full   -> them cac test stress luoi lon nhieu dot ngap
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

def clone_graph(graph):
    """Sao chep sau cap canh de cac dot cap nhat ngap dong khong lam thay doi do thi goc."""
    return {
        u: {v: (dict(e) if isinstance(e, dict) else e) for v, e in nbrs.items()}
        for u, nbrs in graph.items()
    }

class FloodGraphProblem(GraphProblem):
    """
    C_v = nguong chiu ngap (cm), alpha = he so phat.
    `locations` (tuy chon) = toa do cho heuristic Euclid.
    `dynamic_updates` (tuy chon) = danh sach cac su kien thay doi ngap theo thoi gian thuc:
        [{"new_start": node_hoac_None, "flood_changes": {(u, v): new_flood, ...}}, ...]
    """
    def __init__(self, initial, goal, graph, C_v=60, alpha=2, locations=None, dynamic_updates=None):
        super().__init__(initial, goal, graph)
        self.C_v, self.alpha, self.locations = C_v, alpha, locations
        self.dynamic_updates = list(dynamic_updates) if dynamic_updates else []

    def step_cost(self, s, a, s2):                      # OVERRIDE
        edge = self.graph[s][a]
        d, f = edge["distance"], edge["flood"]
        if f >= self.C_v:                               # rang buoc an toan cung
            return INF
        return d * (1 + self.alpha * (f / self.C_v))

# ======================= TIEN ICH DUNG CHUNG CHO CAC SOLVER =======================
def _eq(a, b):
    """So sanh bang an toan cho float va INF (vi math.isclose(INF, INF) == False)."""
    if a == b:
        return True
    if a == INF or b == INF:
        return False
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)

def _less_key(k1, k2):
    """So sanh tu dien (lexicographical) 2 khoa (k1, k2) cua D* Lite voi sai so so thuc."""
    if not _eq(k1[0], k2[0]):
        return k1[0] < k2[0]
    return (not _eq(k1[1], k2[1])) and (k1[1] < k2[1])

def _normalize_problem(problem, copy_graph=False):
    """Nhan GraphProblem-like hoac dict {"graph","start","goal",...} (Section 12) -> GraphProblem-like."""
    if isinstance(problem, dict):
        g = clone_graph(problem["graph"]) if copy_graph else problem["graph"]
        start, goal = problem["start"], problem["goal"]
        sample = next((e for nb in g.values() for e in nb.values()), None)
        if isinstance(sample, dict):
            p = FloodGraphProblem(
                start, goal, g,
                C_v=problem.get("C_v", 60),
                alpha=problem.get("alpha", 2),
                locations=problem.get("locations"),
                dynamic_updates=problem.get("dynamic_updates")
            )
        else:
            p = GraphProblem(start, goal, g)
            p.locations = problem.get("locations")
            p.dynamic_updates = list(problem.get("dynamic_updates", []))
        return p
    if copy_graph:
        g_copy = clone_graph(problem.graph)
        if isinstance(problem, FloodGraphProblem):
            return FloodGraphProblem(
                problem.initial, problem.goal, g_copy,
                C_v=problem.C_v, alpha=problem.alpha,
                locations=getattr(problem, "locations", None),
                dynamic_updates=getattr(problem, "dynamic_updates", None)
            )
        p = GraphProblem(problem.initial, problem.goal, g_copy)
        p.locations = getattr(problem, "locations", None)
        p.dynamic_updates = list(getattr(problem, "dynamic_updates", []))
        return p
    return problem

def _apply_edge_change(problem, u, v, new_val):
    """Cap nhat do ngap (hoac trong so) cua canh (u, v) va (v, u) tren do thi."""
    if v in problem.graph.get(u, {}):
        if isinstance(problem.graph[u][v], dict):
            problem.graph[u][v]["flood"] = new_val
        else:
            problem.graph[u][v] = new_val
    if u in problem.graph.get(v, {}):
        if isinstance(problem.graph[v][u], dict):
            problem.graph[v][u]["flood"] = new_val
        else:
            problem.graph[v][u] = new_val

def _final_problem_snapshot(problem):
    """Tra ve trang thai problem cuoi cung sau khi ap dung tat ca dynamic_updates (dung de verify ground-truth)."""
    updates = problem.get("dynamic_updates") if isinstance(problem, dict) else getattr(problem, "dynamic_updates", None)
    if not updates:
        return _normalize_problem(problem, copy_graph=False)
    p = _normalize_problem(problem, copy_graph=True)
    for ev in updates:
        if ev.get("new_start") is not None:
            p.initial = ev["new_start"]
        for (u, v), f_val in ev.get("flood_changes", {}).items():
            _apply_edge_change(p, u, v, f_val)
    p.dynamic_updates = []
    return p

def _heuristic_pair(problem):
    """
    Tra ve (h_between(a, b), h_name).
    D* Lite can tinh h(s_start, s) va h(s_last, s_start) giua 2 dinh bat ky.
    """
    loc = getattr(problem, "locations", None)
    if loc is None:
        return (lambda a, b: 0.0), "zero(no locations)"
    return (lambda a, b: math.hypot(loc[a][0] - loc[b][0], loc[a][1] - loc[b][1])), "euclid"

def _result(path, cost, expanded, extra):
    return {"path": path, "cost": cost, "expanded": expanded, "extra": extra}

# ======================= D* LITE DAY DU (SAN PHAM CHINH - Koenig & Likhachev 2002) =======================
class DStarLitePlanner:
    """
    Cai dat day du thuat toan D* Lite (Koenig & Likhachev, AAAI 2002 - Figure 4 Optimized):
    - Tim kiem nguoc tu s_goal ve s_start.
    - Duy tri g(s), rhs(s), bien tich luy heuristic k_m, va hang doi uu tien U voi khoa kep:
          CalculateKey(s) = (min(g(s), rhs(s)) + h(s_start, s) + k_m, min(g(s), rhs(s)))
    - Khi canh thay doi trong so va/hoac tac nhan di chuyen sang s_start moi:
          k_m += h(s_last, s_start); s_last = s_start
          Cap nhat chi phi canh (u, v) va goi update_vertex(u), update_vertex(v), roi compute_shortest_path().
    """
    def __init__(self, problem):
        self.problem = problem
        self.h, self.h_name = _heuristic_pair(problem)
        self.s_start = problem.initial
        self.s_goal = problem.goal
        self.s_last = self.s_start
        self.km = 0.0

        nodes = set(problem.graph.keys())
        for nbrs in problem.graph.values():
            nodes.update(nbrs.keys())
        nodes.add(self.s_start)
        nodes.add(self.s_goal)

        self.preds = {u: [] for u in nodes}
        for u, nbrs in problem.graph.items():
            for v in nbrs:
                self.preds[v].append(u)

        self.g = {u: INF for u in nodes}
        self.rhs = {u: INF for u in nodes}
        self.rhs[self.s_goal] = 0.0

        self.cnt = count()
        self.U = []
        self.in_U = {}                                  # u -> (k1, k2) hien tai trong U (lazy deletion O(1))
        self.expanded = 0
        self.peak_frontier = 0

        k_goal = self.calculate_key(self.s_goal)
        self._insert_or_update(self.s_goal, k_goal)

    def calculate_key(self, s):
        m = min(self.g[s], self.rhs[s])
        return (m + self.h(self.s_start, s) + self.km, m)

    def _insert_or_update(self, u, k):
        self.in_U[u] = k
        heapq.heappush(self.U, (k[0], k[1], next(self.cnt), u))
        if len(self.in_U) > self.peak_frontier:
            self.peak_frontier = len(self.in_U)

    def _top_key(self):
        while self.U:
            k1, k2, _, u = self.U[0]
            if self.in_U.get(u) == (k1, k2):
                return (k1, k2)
            heapq.heappop(self.U)
        return (INF, INF)

    def _pop_u(self):
        while self.U:
            k1, k2, _, u = heapq.heappop(self.U)
            if self.in_U.get(u) == (k1, k2):
                del self.in_U[u]
                return u, (k1, k2)
        return None, (INF, INF)

    def _compute_rhs(self, u):
        if u == self.s_goal:
            return 0.0
        best = INF
        for s_next in self.problem.actions(u):
            c = self.problem.step_cost(u, s_next, s_next)
            if c != INF and self.g[s_next] != INF:
                val = c + self.g[s_next]
                if val < best:
                    best = val
        return best

    def update_vertex(self, u):
        if u != self.s_goal:
            self.rhs[u] = self._compute_rhs(u)
        if not _eq(self.g[u], self.rhs[u]):
            self._insert_or_update(u, self.calculate_key(u))
        else:
            self.in_U.pop(u, None)

    def compute_shortest_path(self):
        while _less_key(self._top_key(), self.calculate_key(self.s_start)) or not _eq(self.rhs[self.s_start], self.g[self.s_start]):
            u, k_old = self._pop_u()
            if u is None:
                break
            k_new = self.calculate_key(u)
            if _less_key(k_old, k_new):
                # Chi cap nhat lai khoa do k_m tang, chua phai buoc mo rong dinh
                self._insert_or_update(u, k_new)
            elif self.g[u] > self.rhs[u]:
                # Overconsistent: da tim thay duong tot hon toi s_goal
                self.expanded += 1
                self.g[u] = self.rhs[u]
                for p in self.preds[u]:
                    self.update_vertex(p)
            else:
                # Underconsistent: chi phi tang (do duong ngap), vo hieu hoa g[u] cu va lan truyen
                self.expanded += 1
                self.g[u] = INF
                self.update_vertex(u)
                for p in self.preds[u]:
                    self.update_vertex(p)

    def apply_dynamic_event(self, new_start=None, flood_changes=None):
        """Cap nhat vi tri s_start (cong don k_m) va sua cuc bo cac canh thay doi do ngap."""
        if new_start is not None and new_start != self.s_start:
            self.km += self.h(self.s_last, new_start)
            self.s_last = new_start
            self.s_start = new_start
            self.problem.initial = new_start
        if flood_changes:
            affected = set()
            for (u, v), new_f in flood_changes.items():
                _apply_edge_change(self.problem, u, v, new_f)
                affected.add(u)
                affected.add(v)
            for u in affected:
                self.update_vertex(u)
        self.compute_shortest_path()

    def extract_path(self):
        """Trich xuat duong di ngan nhat tu s_start hien tai ve s_goal theo bang g(s)."""
        if self.g[self.s_start] == INF:
            return None, INF
        path = [self.s_start]
        curr = self.s_start
        visited = {curr}
        total_cost = 0.0
        while not self.problem.goal_test(curr):
            best_next = None
            best_rank = None
            for v in self.problem.actions(curr):
                if v in visited:
                    continue
                c = self.problem.step_cost(curr, v, v)
                if c == INF or self.g[v] == INF:
                    continue
                val = c + self.g[v]
                # Uu tien dinh tren cay ngan nhat da consistent (val == g[curr] va g[v] == rhs[v])
                exact_tree = 0 if (_eq(val, self.g[curr]) and _eq(self.g[v], self.rhs[v])) else 1
                rank = (exact_tree, round(val, 9), round(self.g[v], 9))
                if best_rank is None or rank < best_rank:
                    best_rank = rank
                    best_next = v
            if best_next is None:
                return None, INF
            total_cost += self.problem.step_cost(curr, best_next, best_next)
            curr = best_next
            visited.add(curr)
            path.append(curr)
        return path, total_cost


def solve_d_star_lite(problem):
    """
    Ham giai D* Lite theo giao dien chung Section 5.
    - Neu problem tinh: chay 1 pha compute_shortest_path().
    - Neu problem co `dynamic_updates`: chay pha khoi tao + cac pha replan cuc bo voi k_m.
    """
    has_updates = bool(problem.get("dynamic_updates") if isinstance(problem, dict) else getattr(problem, "dynamic_updates", None))
    prob = _normalize_problem(problem, copy_graph=has_updates)
    planner = DStarLitePlanner(prob)
    planner.compute_shortest_path()
    init_expanded = planner.expanded
    iterations = 1

    for ev in getattr(prob, "dynamic_updates", []):
        planner.apply_dynamic_event(new_start=ev.get("new_start"), flood_changes=ev.get("flood_changes"))
        iterations += 1

    path, cost = planner.extract_path()
    extra = {
        "iterations": iterations,
        "peak_frontier": planner.peak_frontier,
        "init_expanded": init_expanded,
        "replan_expanded": planner.expanded - init_expanded,
        "km": round(planner.km, 4),
        "heuristic": planner.h_name
    }
    return _result(path, cost, planner.expanded, extra)

solve = solve_d_star_lite                               # ham `solve` ma Duc se goi

# ======================= A* BASELINE (Lec4) cung giao dien =======================
def _astar_single_run(problem, h):
    """Chay 1 lan A* chuan Lec4 tren trang thai do thi hien tai."""
    expanded, peak_frontier = 0, 0
    start = Node(problem.initial)
    cnt = count()
    frontier = [(h(start.state, problem.goal), next(cnt), start)]
    best_g = {start.state: 0.0}
    peak_frontier = 1
    while frontier:
        _, _, node = heapq.heappop(frontier)
        if node.path_cost > best_g.get(node.state, INF) + 1e-9:  # stale
            continue
        expanded += 1
        if problem.goal_test(node.state):
            return node.solution(), node.path_cost, expanded, peak_frontier
        for child in node.expand(problem):
            g2 = child.path_cost
            if g2 != INF and g2 + 1e-9 < best_g.get(child.state, INF):
                best_g[child.state] = g2
                heapq.heappush(frontier, (g2 + h(child.state, problem.goal), next(cnt), child))
        if len(frontier) > peak_frontier:
            peak_frontier = len(frontier)
    return None, INF, expanded, peak_frontier

def solve_astar(problem):
    """
    A* baseline y het Lec4, cung giao dien va cung dinh nghia expanded.
    Khi co `dynamic_updates` (canh ngap thay doi), A* khong co co che sua cay cuc bo nen phai
    xoa frontier va chay lai A* tu dau tren ban do moi.
    """
    has_updates = bool(problem.get("dynamic_updates") if isinstance(problem, dict) else getattr(problem, "dynamic_updates", None))
    prob = _normalize_problem(problem, copy_graph=has_updates)
    h, h_name = _heuristic_pair(prob)

    path, cost, total_expanded, peak_frontier = _astar_single_run(prob, h)
    init_expanded = total_expanded
    iterations = 1

    for ev in getattr(prob, "dynamic_updates", []):
        if ev.get("new_start") is not None:
            prob.initial = ev["new_start"]
        for (u, v), new_f in ev.get("flood_changes", {}).items():
            _apply_edge_change(prob, u, v, new_f)
        path, cost, exp_i, pf_i = _astar_single_run(prob, h)
        total_expanded += exp_i
        peak_frontier = max(peak_frontier, pf_i)
        iterations += 1

    extra = {
        "iterations": iterations,
        "peak_frontier": peak_frontier,
        "init_expanded": init_expanded,
        "replan_expanded": total_expanded - init_expanded,
        "heuristic": h_name
    }
    return _result(path, cost, total_expanded, extra)

# ======================= KIEM TRA CORRECTNESS (Section 9, 10, 26) =======================
def optimal_cost_reference(problem):
    """Dijkstra doc lap tren trang thai ban do cuoi cung dung lam 'ground truth' cho optimality."""
    problem = _final_problem_snapshot(problem)
    best, cnt = {problem.initial: 0.0}, count()
    pq = [(0.0, next(cnt), problem.initial)]
    while pq:
        d, _, u = heapq.heappop(pq)
        if d > best.get(u, INF) + 1e-9:
            continue
        if problem.goal_test(u):
            return d
        for v in problem.actions(u):
            c = problem.step_cost(u, v, v)
            if c == INF:
                continue
            nd = d + c
            if nd + 1e-9 < best.get(v, INF):
                best[v] = nd
                heapq.heappush(pq, (nd, next(cnt), v))
    return INF

def verify_result(problem, result, reference_cost=None, require_optimal=False):
    """Tra ve (ok, ly_do). Kiem tra: key bat buoc, start/goal, tung canh ton tai & huu han, cost == tong cost, optimality."""
    problem = _final_problem_snapshot(problem)
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
    total = 0.0
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
    """Kiem tra dieu kien du cho admissible & consistent: Euclid(u,v) <= step_cost(u,v) tren moi canh huu han."""
    problem = _final_problem_snapshot(problem)
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
def make_test(test_id, category, graph, start, goal, locations, description, reps=1, C_v=60, alpha=2, dynamic_updates=None):
    return {
        "test_id": test_id, "category": category, "graph": graph, "start": start, "goal": goal,
        "locations": locations, "C_v": C_v, "alpha": alpha,
        "dynamic_updates": dynamic_updates or [], "description": description, "reps": reps
    }

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
                    f = flood_fn(rnd)
                    G[(r, c)][(r2, c2)] = {"distance": spacing, "flood": f}
                    G.setdefault((r2, c2), {})[(r, c)] = {"distance": spacing, "flood": f}
    return G, loc

def generate_grid_flood_waves(n, num_waves, seed=99):
    """Sinh danh sach cac dot cap nhat ngap cuc bo gan phia start/giua ban do khi xe dang di chuyen."""
    rnd = random.Random(seed)
    waves = []
    cur_r, cur_c = 0, 0
    for w in range(num_waves):
        if w % 2 == 0 and cur_r < n // 3:
            cur_r += 1
        elif cur_c < n // 3:
            cur_c += 1
        changes = {}
        for _ in range(3):
            r = rnd.randint(max(0, cur_r), min(n - 2, n // 2 + 1))
            c = rnd.randint(max(0, cur_c), min(n - 2, n // 2 + 1))
            u = (r, c)
            v = (r + 1, c) if rnd.random() < 0.5 else (r, c + 1)
            changes[(u, v)] = round(rnd.uniform(25.0, 65.0), 1)
        waves.append({"new_start": (cur_r, cur_c), "flood_changes": changes})
    return waves

def get_tests(full=False):
    loc = romania_map["locations"]
    dist = make_undirected(romania_map["roads"])
    rnd_flood = wrap_graph(dist, seed=42, max_flood=55)
    blocked = wrap_graph(dist, flood_map={("Rimnicu", "Pitesti"): 65}, seed=42, max_flood=55)
    T = []

    # 1. BASELINE: ban do Romania cua co (ca tinh va dong)
    T.append(make_test("baseline_romania_arad_bucharest", "BASELINE", rnd_flood, "Arad", "Bucharest", loc,
                       "Romania (teacher map), static flood random seed=42 in [0,55] cm.", reps=200))
    T.append(make_test("baseline_romania_oradea_giurgiu", "BASELINE", rnd_flood, "Oradea", "Giurgiu", loc,
                       "Romania, static flood field, longer route (6 nodes).", reps=200))
    T.append(make_test("baseline_romania_iasi_craiova", "BASELINE", rnd_flood, "Iasi", "Craiova", loc,
                       "Romania, static flood field, start in the north-east corner.", reps=200))
    T.append(make_test("baseline_romania_blocked_edge", "BASELINE", blocked, "Arad", "Bucharest", loc,
                       "Romania with Rimnicu-Pitesti flooded at 65 cm >= C_v: route detours via Fagaras.", reps=200))
    T.append(make_test("baseline_romania_dynamic_replan", "BASELINE", rnd_flood, "Arad", "Bucharest", loc,
                       "Romania dynamic: vehicle moves Arad->Sibiu, then Rimnicu-Pitesti floods (65 cm >= C_v) and Fagaras-Bucharest floods to 20 cm.",
                       reps=200,
                       dynamic_updates=[
                           {"new_start": "Sibiu", "flood_changes": {("Rimnicu", "Pitesti"): 65.0}},
                           {"new_start": "Sibiu", "flood_changes": {("Fagaras", "Bucharest"): 20.0}}
                       ]))

    # 2. BEST_CASE: Ban do dong co nhieu dot bao ngap cuc bo phia gan xe (ngon cay tim kiem D* Lite)
    G6, L6 = grid_graph(6, lambda r: round(r.uniform(0, 20), 1), seed=11)
    T.append(make_test("best_dynamic_grid6x6_local_waves", "BEST_CASE", G6, (0, 0), (5, 5), L6,
                       "6x6 grid with 5 local flood updates near the moving vehicle: D* Lite repairs only leaf nodes, A* replans from scratch.",
                       reps=50, dynamic_updates=generate_grid_flood_waves(6, 5, seed=101)))

    G8, L8 = grid_graph(8, lambda r: round(r.uniform(0, 20), 1), seed=12)
    T.append(make_test("best_dynamic_grid8x8_local_waves", "BEST_CASE", G8, (0, 0), (7, 7), L8,
                       "8x8 grid with 8 local flood updates near start/mid-route: strong incremental repair advantage for D* Lite.",
                       reps=30, dynamic_updates=generate_grid_flood_waves(8, 8, seed=202)))

    # 3. WORST_CASE: Ban do tinh hoan toan (khong co cap nhat) HOAC ngap sat dinh Goal (goc cay D* Lite)
    G7_static, L7_static = grid_graph(7, lambda r: round(r.uniform(0, 50), 1), seed=21)
    T.append(make_test("worst_static_grid7x7_no_updates", "WORST_CASE", G7_static, (0, 0), (6, 6), L7_static,
                       "Purely static 7x7 grid (0 updates): D* Lite pays overhead of maintaining g/rhs/2-tuple keys without reusing the search tree.",
                       reps=40))

    G7_root, L7_root = grid_graph(7, lambda r: round(r.uniform(0, 25), 1), seed=22)
    root_Goal_waves = [
        {"new_start": (0, 0), "flood_changes": {((5, 6), (6, 6)): 65.0, ((6, 5), (6, 6)): 55.0}},
        {"new_start": (0, 1), "flood_changes": {((4, 6), (5, 6)): 58.0, ((6, 4), (6, 5)): 65.0}},
    ]
    T.append(make_test("worst_dynamic_grid7x7_goal_root_flood", "WORST_CASE", G7_root, (0, 0), (6, 6), L7_root,
                       "7x7 grid where flood changes hit edges directly adjacent to Goal (root of D* Lite tree), forcing cascading tree invalidation.",
                       reps=40, dynamic_updates=root_Goal_waves))

    # 4. STRESS: Tang kich thuoc luoi va so dot cap nhat ngap theo thoi gian thuc
    stress_configs = [(6, 6), (8, 10), (10, 12), (12, 15)] + ([(15, 20)] if full else [])
    for n, waves in stress_configs:
        G_s, L_s = grid_graph(n, lambda r: round(r.uniform(0, 30), 1), seed=30 + n)
        T.append(make_test(
            f"stress_grid{n}x{n}_{waves}waves", "STRESS", G_s, (0, 0), (n - 1, n - 1), L_s,
            f"{n}x{n} urban grid with {waves} sequential real-time flood reports.",
            reps=10 if n <= 10 else 3,
            dynamic_updates=generate_grid_flood_waves(n, waves, seed=500 + n)
        ))
    return T

def problem_from_test(t):
    return FloodGraphProblem(
        t["start"], t["goal"], t["graph"],
        C_v=t["C_v"], alpha=t["alpha"],
        locations=t["locations"], dynamic_updates=t["dynamic_updates"]
    )

# ======================= SELF-TEST (Section 26) =======================
def self_test():
    loc = romania_map["locations"]
    dist = make_undirected(romania_map["roads"])
    dry = wrap_graph(dist, flood_map={}, max_flood=0)
    rnd = wrap_graph(dist, seed=42, max_flood=55)
    block_goal = wrap_graph(dist, flood_map={("Bucharest", v): 65 for v in dist["Bucharest"]}, seed=42, max_flood=55)
    dyn_prob = FloodGraphProblem(
        "Arad", "Bucharest", rnd, locations=loc,
        dynamic_updates=[{"new_start": "Sibiu", "flood_changes": {("Rimnicu", "Pitesti"): 65.0}}]
    )
    cases = [
        ("dry Arad->Bucharest (known optimum 418)", FloodGraphProblem("Arad", "Bucharest", dry, locations=loc), 418),
        ("random flood Arad->Bucharest", FloodGraphProblem("Arad", "Bucharest", rnd, locations=loc), None),
        ("blocked Rimnicu-Pitesti", FloodGraphProblem("Arad", "Bucharest", wrap_graph(dist, flood_map={("Rimnicu", "Pitesti"): 65}, seed=42, max_flood=55), locations=loc), None),
        ("dynamic replan at Sibiu (Rimnicu-Pitesti flooded)", dyn_prob, None),
        ("start == goal", FloodGraphProblem("Arad", "Arad", rnd, locations=loc), 0),
        ("unreachable goal (all Bucharest roads flooded)", FloodGraphProblem("Arad", "Bucharest", block_goal, locations=loc), INF),
        ("dict input (Section 12) Oradea->Giurgiu", {"graph": rnd, "start": "Oradea", "goal": "Giurgiu", "locations": loc}, None),
    ]
    all_ok = True
    for name, prob, known in cases:
        ref = optimal_cost_reference(prob)
        if known is not None:
            assert math.isclose(ref, known) or (ref == known == INF), f"oracle {ref} != known {known}"
        for solver, need_opt in ((solve, True), (solve_astar, True)):
            r = solver(prob)
            ok, why = verify_result(prob, r, reference_cost=ref, require_optimal=need_opt)
            all_ok &= ok
            print(f"[{'PASS' if ok else 'FAIL'}] {name:<50} {solver.__name__:<20} cost={r['cost'] if r['cost']==INF else round(r['cost'],2)} "
                  f"expanded={r['expanded']} extra={ {k: (round(v,2) if isinstance(v,float) else v) for k,v in r['extra'].items()} } {'' if ok else '-> '+why}")
    adm = heuristic_admissible_on_edges(FloodGraphProblem("Arad", "Bucharest", rnd, locations=loc))
    print(f"[{'PASS' if adm else 'FAIL'}] heuristic Euclid <= step_cost tren moi canh Romania (admissible & consistent)")
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
    out("| Test | Category | Algorithm | Status | Cost | Expanded | Replan Exp | Iterations | Peak frontier | Time (ms) | Memory (KB) |")
    out("|---|---|---|---|---|---|---|---|---|---|---|")
    notes = []
    for t in get_tests(full):
        prob = problem_from_test(t)
        ref = optimal_cost_reference(prob)
        for name, solver, need_opt in (("A* (baseline)", solve_astar, True), ("D* Lite", solve, True)):
            b = benchmark(solver, prob, t["reps"])
            if b["status"] == "OK":
                ok, why = verify_result(prob, b["result"], reference_cost=ref, require_optimal=need_opt)
                if not ok:
                    b = {"status": "FAILED", "reason": why}
            if b["status"] != "OK":
                out(f"| {t['test_id']} | {t['category']} | {name} | FAILED | - | - | - | - | - | - | - |")
                notes.append(f"FAILED {t['test_id']} {name}: {b['reason']}")
                continue
            r = b["result"]; x = r["extra"]
            out(f"| {t['test_id']} | {t['category']} | {name} | PASS | {fmt(r['cost'])} | {r['expanded']} | "
                f"{x['replan_expanded']} | {x['iterations']} | {x['peak_frontier']} | {b['time_ms']:.3f} | {b['memory_kb']:.1f} |")
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