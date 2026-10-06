"""
DFS -> IDA* benchmark tren bai toan dinh tuyen tranh ngap lut.
Baseline tu file Lec3 & Lec4 cua co Dung
Dinh dang tra ve chung cua ca team: return path, cost, st
    st = {"expanded": int, "peak_struct": int, "iterations": int}
"""
import heapq, math, random, time, tracemalloc
from itertools import count

INF = float("inf")

# ======================= BASELINE CUA CO (Lec3/Lec4) =======================
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

# ======================= NHIEM VU 1: MO HINH NGAP LUT =======================
def wrap_graph(undirected_graph, flood_map=None, seed=42, max_flood=55.0, decimals=1):
    """
    {u: {v: d}}  ->  {u: {v: {'distance': d, 'flood': f}}}
    - flood_map: dict {(u, v): f} de TRUYEN VAO do ngap cu the (ap dung ca 2 chieu).
    - Canh khong co trong flood_map: gia lap ngau nhien f ~ U(0, max_flood), lam tron `decimals` chu so.
    - Do ngap la thuoc tinh cua DOAN DUONG nen 2 chieu u-v va v-u dung chung 1 gia tri.
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
    """GraphProblem co rang buoc ngap lut: C_v = nguong chiu ngap (cm), alpha = he so phat."""
    def __init__(self, initial, goal, graph, C_v=60, alpha=2):
        super().__init__(initial, goal, graph)
        self.C_v = C_v
        self.alpha = alpha

    def step_cost(self, s, a, s2):                      # OVERRIDE
        edge = self.graph[s][a]
        d, f = edge["distance"], edge["flood"]
        if f >= self.C_v:                               # rang buoc an toan: duong khong di duoc
            return INF
        return d * (1 + self.alpha * (f / self.C_v))

# ======================= NHIEM VU 2: DFS / IDA* / A* =======================
def straight_line_distance(locations, a, b):
    (x1, y1), (x2, y2) = locations[a], locations[b]
    return math.hypot(x1 - x2, y1 - y2)

def dfs_benchmark(problem):
    """
    DFS y het Lec3 (stack LIFO + explored set), them bo dem.
    expanded += 1 ngay truoc khi bung dinh con; peak_struct = max(len(stack) + len(explored)).
    Luu y: DFS goc KHONG nhin step_cost nen se di xuyen duong ngap (cost = inf).
    De dam bao an toan, bo qua con co path_cost == inf (tuong duong coi nhu khong co canh).
    """
    st = {"expanded": 0, "peak_struct": 0, "iterations": 1}
    stack = [Node(problem.initial)]
    explored = set()
    while stack:
        node = stack.pop()
        if problem.goal_test(node.state):
            return node.solution(), node.path_cost, st
        if node.state in explored:
            continue
        explored.add(node.state)
        st["expanded"] += 1
        stack.extend(c for c in node.expand(problem) if c.path_cost != INF)
        st["peak_struct"] = max(st["peak_struct"], len(stack) + len(explored))
    return None, INF, st

def ida_star_benchmark(problem, locations, max_expanded=None):
    """
    IDA* = lap lai DFS gioi han theo nguong f = g + h (h = Euclid chim bay, admissible vi cost >= distance >= Euclid).
    - KHONG co explored / bang g toan cuc: chi giu duong di hien tai (stack) + on_path de tranh vong lap.
    - peak_struct  = max(len(path))
    - iterations   = so luot quet (ban dau 1; moi lan phai nang threshold len f nho nhat bi cat thi +1)
    - expanded     = so lan mot dinh HOP LE (khong nam tren duong hien tai, cost huu han, f <= threshold)
                     duoc lay ra de duyet (ke ca root va dinh dich).
    - max_expanded : tran an toan cho worst-case; vuot tran -> tra (None, inf, st) voi st["aborted"] = True.
    Cai dat bang stack tuong minh (khong de quy) de khong dinh gioi han recursion cua Python.
    """
    goal = problem.goal
    h = lambda s: straight_line_distance(locations, s, goal)
    st = {"expanded": 0, "peak_struct": 0, "iterations": 1}
    root = Node(problem.initial)
    threshold = h(root.state)

    while True:
        next_threshold = INF
        on_path = {root.state}
        st["expanded"] += 1
        if problem.goal_test(root.state):
            return root.solution(), 0, st
        stack = [(root, root.expand(problem))]          # stack chinh la duong di hien tai
        st["peak_struct"] = max(st["peak_struct"], len(stack))

        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:                           # het con -> quay lui
                on_path.discard(node.state)
                stack.pop()
                continue
            if child.state in on_path:                  # tranh vong lap tren duong hien tai
                continue
            f = child.path_cost + h(child.state)        # cost = inf (duong ngap) -> f = inf -> bi cat
            if f > threshold:
                next_threshold = min(next_threshold, f)
                continue
            st["expanded"] += 1                         # dinh hop le duoc lay ra duyet
            if max_expanded and st["expanded"] > max_expanded:
                st["aborted"] = True
                return None, INF, st
            if problem.goal_test(child.state):
                return child.solution(), child.path_cost, st
            on_path.add(child.state)
            stack.append((child, child.expand(problem)))
            st["peak_struct"] = max(st["peak_struct"], len(stack))

        if next_threshold == INF:                       # khong con gi de nang nguong -> vo nghiem
            return None, INF, st
        threshold = next_threshold
        st["iterations"] += 1

def astar_benchmark(problem, locations):
    """A* y het Lec4 (best_g + heap), them bo dem. peak_struct = max(len(frontier) + len(best_g))."""
    goal = problem.goal
    h = lambda s: straight_line_distance(locations, s, goal)
    st = {"expanded": 0, "peak_struct": 0, "iterations": 1}
    start = Node(problem.initial)
    cnt = count()
    frontier = [(h(start.state), next(cnt), start)]
    best_g = {start.state: 0}
    while frontier:
        _, _, node = heapq.heappop(frontier)
        if node.path_cost > best_g.get(node.state, INF):
            continue
        st["expanded"] += 1
        if problem.goal_test(node.state):
            return node.solution(), node.path_cost, st
        for child in node.expand(problem):
            g2 = child.path_cost
            if g2 < best_g.get(child.state, INF):
                best_g[child.state] = g2
                heapq.heappush(frontier, (g2 + h(child.state), next(cnt), child))
        st["peak_struct"] = max(st["peak_struct"], len(frontier) + len(best_g))
    return None, INF, st

# ======================= WRAPPER DO THOI GIAN / RAM THAT =======================
def measure(algo, problem, locations=None, reps=1, **kw):
    """
    Tra ve cost, expanded, iterations, peak_struct, ms (TB `reps` lan), mem_kb (tracemalloc peak).
    reps = 0 : chi chay DUNG 1 LAN, lay thoi gian ngay lan do va bo qua tracemalloc (cho worst-case rat nang).
    """
    call = (lambda: algo(problem, locations, **kw)) if locations is not None else (lambda: algo(problem))
    if reps == 0:
        t0 = time.perf_counter()
        path, cost, st = call()
        return {"path": path, "cost": cost, "ms": (time.perf_counter() - t0) * 1000,
                "mem_kb": float("nan"), **st}
    path, cost, st = call()
    t0 = time.perf_counter()
    for _ in range(reps):
        call()
    ms = (time.perf_counter() - t0) / reps * 1000
    tracemalloc.start()
    call()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"path": path, "cost": cost, "ms": ms, "mem_kb": peak / 1024, **st}

def fmt_cost(c):
    return "inf" if c == INF else f"{c:.2f}"

def run_compare(title, problem, locations, reps=200, with_dfs=True, max_expanded=None, verbose=True):
    rows = []
    algos = []
    if with_dfs:
        algos.append(("DFS", dfs_benchmark, None, {}))
    algos.append(("IDA*", ida_star_benchmark, locations, {"max_expanded": max_expanded} if max_expanded else {}))
    algos.append(("A*", astar_benchmark, locations, {}))
    if verbose:
        print(f"\n### {title}")
        print("| Thuat toan | Cost | Expanded | Iterations | Peak struct | Time (ms) | Peak mem (KB) |")
        print("|---|---|---|---|---|---|---|")
    for name, fn, loc, kw in algos:
        r = measure(fn, problem, loc, reps, **kw)
        r["name"] = name
        rows.append(r)
        if verbose:
            tag = " (ABORT)" if r.get("aborted") else ""
            print(f"| {name}{tag} | {fmt_cost(r['cost'])} | {r['expanded']} | {r['iterations']} | "
                  f"{r['peak_struct']} | {r['ms']:.3f} | {r['mem_kb']:.1f} |")
    if verbose:
        for r in rows:
            if r["path"]:
                p = list(map(str, r["path"]))
                txt = " -> ".join(p) if len(p) <= 10 else " -> ".join(p[:3]) + f" -> ... ({len(p)} dinh) ... -> " + " -> ".join(p[-2:])
                print(f"  {r['name']:<5}: {txt}")
    return rows

# ======================= BO TEST TONG HOP =======================
def grid_flood_problem(n, flood_fn, spacing=10.0, seed=7):
    """
    Luoi duong pho n x n (4 huong), distance = spacing. Goc (0,0) -> goc (n-1,n-1).
    flood_fn(rnd) sinh do ngap tung canh. Euclid (duong cheo) < Manhattan nen h KHONG chinh xac
    -> nhieu duong di don gian co chi phi gan bang nhau -> dung de kich worst-case cua IDA*.
    """
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
    return FloodGraphProblem((0, 0), (n - 1, n - 1), G), loc

def corridor_problem(n, spacing=10.0):
    """BEST CASE: hanh lang thang n dinh (flood = 0) + 1 ngo cut moi dinh. h = chi phi that tren truc chinh."""
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
    return FloodGraphProblem(("m", 0), ("m", n - 1), G), loc

def main(full=False):
    loc = romania_map["locations"]
    g_dist = make_undirected(romania_map["roads"])

    # ---------- A. Romania, do ngap ngau nhien (seed co dinh) ----------
    g = wrap_graph(g_dist, seed=42, max_flood=55)
    run_compare("A1. Romania ngap ngau nhien: Arad -> Bucharest", FloodGraphProblem("Arad", "Bucharest", g), loc)
    run_compare("A2. Romania ngap ngau nhien: Oradea -> Giurgiu", FloodGraphProblem("Oradea", "Giurgiu", g), loc)
    run_compare("A3. Romania ngap ngau nhien: Iasi -> Craiova", FloodGraphProblem("Iasi", "Craiova", g), loc)

    # ---------- B. Rang buoc an toan: chan Rimnicu-Pitesti (flood = 65 >= C_v) ----------
    gb = wrap_graph(g_dist, flood_map={("Rimnicu", "Pitesti"): 65}, seed=42, max_flood=55)
    run_compare("B. Chan Rimnicu-Pitesti (flood=65 >= C_v): Arad -> Bucharest",
                FloodGraphProblem("Arad", "Bucharest", gb), loc)

    # ---------- C. BEST CASE ----------
    g0 = wrap_graph(g_dist, flood_map={}, max_flood=0)
    run_compare("C1. BEST (Romania, flood=0): Sibiu -> Fagaras", FloodGraphProblem("Sibiu", "Fagaras", g0), loc)
    p, l = corridor_problem(100)
    run_compare("C2. BEST (hanh lang thang 100 dinh, h chinh xac, flood=0)", p, l, reps=20)

    # ---------- D. WORST CASE: cung do thi luoi, chi doi tinh chat cua flood ----------
    print("\n### D. Worst case: luoi n x n (distance=10), goc -> goc")
    print("| n | Loai flood | Thuat toan | Cost | Expanded | Iterations | Peak struct | Time (ms) | Peak mem (KB) |")
    print("|---|---|---|---|---|---|---|---|---|")
    CAP = 40_000_000
    sizes = (4, 5, 6, 7, 8) + ((9,) if full else ())
    kinds = (("flood = 0", lambda r: 0.0),
             ("luong tu hoa {0,15,30,45}", lambda r: r.choice([0, 15, 30, 45])),
             ("lien tuc (thap phan)", lambda r: round(r.uniform(0, 55), 1)))
    for n in sizes:
        for label, ffn in kinds:
            p, l = grid_flood_problem(n, ffn)
            reps = 1 if n <= 6 else 0
            ri = measure(ida_star_benchmark, p, l, reps, max_expanded=CAP)
            ra = measure(astar_benchmark, p, l, 1 if n <= 6 else 0)
            for name, r in (("IDA*", ri), ("A*", ra)):
                mem = "-" if r["mem_kb"] != r["mem_kb"] else f"{r['mem_kb']:.0f}"
                print(f"| {n} | {label} | {name} | {fmt_cost(r['cost'])} | {r['expanded']} | {r['iterations']} | "
                      f"{r['peak_struct']} | {r['ms']:.2f} | {mem} |", flush=True)

if __name__ == "__main__":
    import sys
    main(full="--full" in sys.argv)
