"""
UCS vs Bidirectional UCS - benchmark 4 chi so: cost, expanded nodes, time, memory.
Baseline (romania_map, GraphProblem, Node, make_undirected) copy nguyen tu Lec3/Lec4 cua co.
Quy tac dem expanded: dem moi lan pop mot node HOP LE (khong stale) khoi hang doi.
Bi-UCS = tong expanded cua forward + backward.
"""
import heapq, time, tracemalloc, random
from itertools import count
from collections import defaultdict

# ======================= BASELINE CUA CO =======================
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

# ======================= UCS (baseline + dem expanded) =======================
def ucs(problem):
    """UCS y het baseline cua co, them bo dem."""
    st = {"expanded": 0, "peak_struct": 0}
    start = Node(problem.initial)
    counter = count()
    frontier = [(0, next(counter), start)]
    explored_cost = {start.state: 0}
    while frontier:
        cost, _, node = heapq.heappop(frontier)
        if cost > explored_cost.get(node.state, float("inf")):
            continue
        st["expanded"] += 1
        if problem.goal_test(node.state):
            return node.solution(), node.path_cost, st
        for child in node.expand(problem):
            g_new = child.path_cost
            if g_new < explored_cost.get(child.state, float("inf")):
                explored_cost[child.state] = g_new
                heapq.heappush(frontier, (g_new, next(counter), child))
        st["peak_struct"] = max(st["peak_struct"], len(frontier) + len(explored_cost))
    return None, float("inf"), st

# ======================= BIDIRECTIONAL UCS =======================
def build_reverse(graph):
    rev = defaultdict(dict)
    for u, nbrs in graph.items():
        for v, w in nbrs.items():
            rev[v][u] = w
    return rev

def bidirectional_ucs(problem, rev=None):
    """
    Forward tu start (dung graph), backward tu goal (dung do thi dao rev).
    Luan phien mo rong ben co top hang doi nho hon.
    mu = min(gF(v)+gB(v)); dung khi topF + topB >= mu.
    """
    graph = problem.graph
    if rev is None:
        rev = build_reverse(graph)
    s, t = problem.initial, problem.goal
    st = {"expanded": 0, "expanded_F": 0, "expanded_B": 0, "peak_struct": 0}
    if s == t:
        return [s], 0, st

    cnt = count()
    gF, gB = {s: 0}, {t: 0}
    parF, parB = {s: None}, {t: None}
    hF, hB = [(0, next(cnt), s)], [(0, next(cnt), t)]
    mu, meet = float("inf"), None

    def clean(heap, g):
        while heap and heap[0][0] > g[heap[0][2]]:
            heapq.heappop(heap)

    while hF and hB:
        clean(hF, gF); clean(hB, gB)
        if not hF or not hB:
            break
        topF, topB = hF[0][0], hB[0][0]
        if topF + topB >= mu:          # dieu kien dung dam bao toi uu
            break
        if topF <= topB:
            side, heap, g, par, other_g, adj = "F", hF, gF, parF, gB, graph
        else:
            side, heap, g, par, other_g, adj = "B", hB, gB, parB, gF, rev
        d, _, u = heapq.heappop(heap)
        st["expanded"] += 1
        st["expanded_" + side] += 1
        for v, w in adj.get(u, {}).items():
            nd = d + w
            if nd < g.get(v, float("inf")):
                g[v] = nd
                par[v] = u
                heapq.heappush(heap, (nd, next(cnt), v))
            if v in other_g and g[v] + other_g[v] < mu:
                mu, meet = g[v] + other_g[v], v
        st["peak_struct"] = max(st["peak_struct"], len(hF) + len(hB) + len(gF) + len(gB))

    if meet is None:
        return None, float("inf"), st
    left, x = [], meet
    while x is not None:
        left.append(x); x = parF[x]
    left.reverse()
    right, x = [], parB[meet]
    while x is not None:
        right.append(x); x = parB[x]
    return left + right, mu, st

# ======================= WRAPPER DO 4 CHI SO =======================
def measure(algo, problem, reps=1, rev=None):
    """Tra ve: cost, expanded, time(ms, trung binh reps lan), peak memory (KB, tracemalloc), peak_struct."""
    call = (lambda: algo(problem, rev)) if algo is bidirectional_ucs else (lambda: algo(problem))
    path, cost, st = call()                      # 1 lan lay ket qua
    t0 = time.perf_counter()
    for _ in range(reps):
        call()
    ms = (time.perf_counter() - t0) / reps * 1000
    tracemalloc.start()
    call()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"path": path, "cost": cost, "expanded": st["expanded"], "ms": ms,
            "mem_kb": peak / 1024, "struct": st["peak_struct"]}

# ======================= BO TEST =======================
def rnd_connected_graph(n, extra_per_node, seed, wmax=20):
    rnd = random.Random(seed)
    G = {i: {} for i in range(n)}
    def add(u, v, w):
        if u != v:
            G[u][v] = w; G[v][u] = w
    for i in range(1, n):
        add(i, rnd.randrange(i), rnd.randint(1, wmax))
    for _ in range(extra_per_node * n):
        add(rnd.randrange(n), rnd.randrange(n), rnd.randint(1, wmax))
    return G

def grid_graph(n, seed, wmax=5):
    rnd = random.Random(seed)
    G = {}
    for r in range(n):
        for c in range(n):
            G.setdefault((r, c), {})
            for dr, dc in ((1, 0), (0, 1)):
                r2, c2 = r + dr, c + dc
                if r2 < n and c2 < n:
                    w = rnd.randint(1, wmax)
                    G[(r, c)][(r2, c2)] = w
                    G.setdefault((r2, c2), {})[(r, c)] = w
    return G

def chain_graph(n):
    G = {i: {} for i in range(n)}
    for i in range(n - 1):
        G[i][i + 1] = 1; G[i + 1][i] = 1
    return G

def hub_graph(chain_len, leaves):
    """DO THI CO HUONG: start -> chain -> hub -> goal; hub co rat nhieu tien nhiem (leaf -> hub).
    Forward di thang, backward bi no vi in-degree cua hub rat lon."""
    G = defaultdict(dict)
    for i in range(chain_len):
        G[("c", i)][("c", i + 1)] = 1
    hub = ("c", chain_len)
    for k in range(leaves):
        G[("leaf", k)][hub] = 1
    G[hub]["goal"] = 1
    return dict(G)

def get_tests():
    tests = []
    g = make_undirected(romania_map["roads"])
    tests.append(("T1 Romania (baseline co): Arad->Bucharest", GraphProblem("Arad", "Bucharest", g), 500))
    tests.append(("T1b Romania: Oradea->Giurgiu", GraphProblem("Oradea", "Giurgiu", g), 500))

    G = grid_graph(60, seed=1)
    tests.append(("T2 BEST: luoi 60x60, goc->goc", GraphProblem((0, 0), (59, 59), G), 5))

    R = rnd_connected_graph(3000, 3, seed=2)
    tests.append(("T3 BEST: do thi ngau nhien day (n=3000), 2 dinh xa", GraphProblem(0, 2999, R), 5))

    u = 0
    v = min(R[u], key=lambda x: R[u][x])
    tests.append(("T4 WORST: start-goal ke nhau (do thi T3)", GraphProblem(u, v, R), 200))

    C = chain_graph(2000)
    tests.append(("T5 WORST: do thi chuoi (b=1), n=2000", GraphProblem(0, 1999, C), 20))

    H = hub_graph(50, 3000)
    tests.append(("T6 WORST: do thi CO HUONG, goal co in-degree lon", GraphProblem(("c", 0), "goal", H), 20))
    return tests

def main():
    lines = []
    def out(s=""):
        print(s); lines.append(s)
    out("| Test | Thuat toan | Cost | Expanded | Time (ms) | Peak mem (KB) | Peak struct |")
    out("|---|---|---|---|---|---|---|")
    for name, prob, reps in get_tests():
        rev = build_reverse(prob.graph)
        a = measure(ucs, prob, reps)
        b = measure(bidirectional_ucs, prob, reps, rev)
        assert abs(a["cost"] - b["cost"]) < 1e-9, f"COST KHAC NHAU o {name}: {a['cost']} vs {b['cost']}"
        for label, r in (("UCS", a), ("Bi-UCS", b)):
            out(f"| {name} | {label} | {r['cost']} | {r['expanded']} | {r['ms']:.3f} | {r['mem_kb']:.0f} | {r['struct']} |")
        out(f"| | *ti le Bi/UCS* | | {b['expanded']/a['expanded']:.2f}x | {b['ms']/a['ms']:.2f}x | {b['mem_kb']/a['mem_kb']:.2f}x | {b['struct']/a['struct']:.2f}x |")
        if name.startswith("T1 "):
            print("  Duong UCS   :", " -> ".join(a["path"]))
            print("  Duong Bi-UCS:", " -> ".join(b["path"]))
    with open("results.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
