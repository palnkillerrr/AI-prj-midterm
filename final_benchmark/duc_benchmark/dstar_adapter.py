"""Stateful adapter for Phuong Anh's D* Lite; one planner per episode."""
import math
from solvers.astar_to_dstarlite import DStarLitePlanner, _normalize_problem


class PlannerAdapter:
    def __init__(self, problem):
        for neighbours in problem["graph"].values():
            for weight in neighbours.values():
                self._check_cost(weight)
        self.planner = DStarLitePlanner(_normalize_problem(problem, copy_graph=True))
        self.previous_expanded = 0

    @staticmethod
    def _check_cost(weight):
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or math.isnan(weight) or weight <= 0:
            raise ValueError("D* Lite dynamic adapter requires strictly positive finite costs; +inf is allowed")

    def update(self, changes):
        planner = self.planner
        # Validate the entire batch before mutating retained state.
        for edge in changes:
            if edge["u"] not in planner.g or edge["v"] not in planner.g:
                raise ValueError("Dynamic updates must use existing vertices")
            self._check_cost(math.inf if edge["cost"] == "inf" else edge["cost"])
        affected = dict.fromkeys(edge["u"] for edge in changes)
        for edge in changes:
            u, v = edge["u"], edge["v"]
            if u not in planner.g or v not in planner.g:
                raise ValueError("Dynamic updates must use existing vertices")
            weight = math.inf if edge["cost"] == "inf" else edge["cost"]
            neighbours = planner.problem.graph.setdefault(u, {})
            if v not in neighbours:
                planner.preds[v].append(u)
            neighbours[v] = weight  # One directed arc; never silently update the reverse.
        for u in affected:
            planner.update_vertex(u)

    def move_start(self, start):
        planner = self.planner
        if start not in planner.g:
            raise ValueError("New start must be an existing vertex")
        if start != planner.s_start:
            planner.km += planner.h(planner.s_last, start)
            planner.s_last = planner.s_start = planner.problem.initial = start

    def plan(self):
        planner = self.planner
        planner.compute_shortest_path()
        path, cost = planner.extract_path()
        expanded = planner.expanded - self.previous_expanded
        self.previous_expanded = planner.expanded
        return {"path": path, "cost": cost, "expanded": expanded,
                "extra": {"peak_frontier": planner.peak_frontier, "km": planner.km,
                          "cumulative_expanded": planner.expanded,
                          "active_queue": len(planner.in_U), "heuristic": planner.h_name}}


def create_planner(problem):
    return PlannerAdapter(problem)
