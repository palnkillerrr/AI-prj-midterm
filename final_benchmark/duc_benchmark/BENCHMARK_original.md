# AI Project Midterm — Common Benchmark & Implementation Specification

## 1. Mục đích

File này là **specification chung bắt buộc** cho toàn bộ project.

Project gồm 3 cặp thuật toán:

1. DFS → IDA*
2. UCS → Bidirectional UCS
3. A* → D* Lite

Mục tiêu của specification:

- Chuẩn hóa interface của cả 3 thuật toán.
- Chuẩn hóa cách đo:
  - Execution Time
  - Memory Consumption
  - Expanded Nodes
- Đảm bảo tất cả thuật toán được chạy trên cùng một bộ test.
- Đảm bảo kết quả có thể kiểm tra correctness.
- Đảm bảo benchmark giữa các thuật toán có ý nghĩa.
- Giữ nguyên bản chất của thuật toán được giao.
- Tạo dữ liệu cuối cùng để tổng hợp vào 3 trang A4.

---

## 2. Vai trò của AI Coding Assistant

Bạn đang hỗ trợ một thành viên trong nhóm chỉnh sửa **thuật toán được giao**.

Bạn phải:

1. Đọc toàn bộ specification này trước khi sửa code.
2. Chỉ sửa phần implementation thuộc thuật toán được giao.
3. Không tự ý thay đổi test cases chung.
4. Không tự ý thay đổi định nghĩa benchmark.
5. Không thay đổi algorithm thành một thuật toán khác.
6. Giữ lại các thành phần cần thiết của implementation hiện tại nếu chúng đúng.
7. Chuẩn hóa output theo interface ở Section 5.
8. Bổ sung các metric còn thiếu.
9. Kiểm tra correctness trước khi benchmark.
10. Báo cáo rõ:
    - file nào đã thay đổi;
    - function nào đã thay đổi;
    - thay đổi để làm gì;
    - cách chạy;
    - kết quả self-test.

---

## 3. Các thuật toán trong project

### 3.1 DFS → IDA*

- Baseline: **DFS**
- Improved algorithm: **IDA\***

IDA* phải giữ đúng bản chất:

- Iterative Deepening.
- Threshold dựa trên `f(n) = g(n) + h(n)`.
- Sử dụng heuristic phù hợp.
- Có cơ chế tránh cycle trên current path.
- Không được biến thành BFS / UCS / A* thông thường.

### 3.2 UCS → Bidirectional UCS

- Baseline: **UCS**
- Improved algorithm: **Bidirectional UCS**

Bidirectional UCS phải:

- Search từ Start → Goal.
- Search từ Goal → Start.
- Duy trì cost của hai phía.
- Có điều kiện stopping chính xác.
- Trả về optimal path.
- Có thể reconstruct path từ hai phía.

Điều kiện dừng phải đảm bảo không làm mất optimal solution.

### 3.3 A* → D* Lite

- Baseline: **A\***
- Improved algorithm: **D\* Lite**

Hai thuật toán phải sử dụng:

- cùng graph;
- cùng start;
- cùng goal;
- cùng edge costs;
- cùng heuristic;
- cùng environment.

D* Lite phải thể hiện khả năng repair/replan khi environment thay đổi.

Không được benchmark A* và D* Lite trên hai bài toán khác nhau.

Ví dụ **KHÔNG hợp lệ**:

```text
A*:      Start = Rimnicu Vilcea, Goal = Bucharest
D* Lite: Start = Arad,           Goal = Bucharest
```

Đây là hai problem khác nhau và không được dùng để so sánh trực tiếp.

---

## 4. Nguyên tắc benchmark chung

Tất cả thuật toán phải được benchmark theo cùng một chuẩn.

Không được để:

```text
Algorithm A: memory = queue size
Algorithm B: memory = tracemalloc peak memory
```

Điều này làm kết quả không thể so sánh công bằng.

Tất cả thuật toán phải sử dụng cùng định nghĩa metric.

---

## 5. Common Solver Interface

Mỗi thuật toán phải cung cấp một function có dạng:

```python
solve(problem) -> result
```

Trong đó:

```python
result = {
    "path": path,
    "cost": cost,
    "expanded": expanded,
    "extra": extra
}
```

### 5.1 `path`

Kiểu: `list`

Ví dụ:

```python
["Arad", "Sibiu", "Rimnicu Vilcea", "Pitesti", "Bucharest"]
```

Yêu cầu:

```python
path[0] == start
path[-1] == goal
```

Nếu không tồn tại đường đi: `path = None`.

### 5.2 `cost`

Tổng cost của path.

```python
cost = 418
```

Nếu không có solution: `cost = float("inf")`.

Không được trả về cost không tương ứng với path.

### 5.3 `expanded`

Số node được algorithm thực sự xử lý.

Định nghĩa chung:

> Một node được tính là **expanded** khi nó được lấy ra khỏi active search structure và được algorithm xử lý/expand.

Ví dụ:

```python
node = heapq.heappop(frontier)
expanded += 1
```

Nếu node goal được lấy ra và kiểm tra trước khi kết thúc thì node đó được tính là expanded.

**Điều quan trọng nhất: cả 3 thuật toán phải dùng cùng một định nghĩa.**

### 5.4 `extra`

Dictionary chứa các metric riêng của thuật toán.

IDA*:

```python
extra = {
    "iterations": iterations,
    "peak_frontier": peak_frontier
}
```

Bidirectional UCS:

```python
extra = {
    "expanded_forward": expanded_forward,
    "expanded_backward": expanded_backward
}
```

D* Lite:

```python
extra = {
    "initial_expanded": initial_expanded,
    "repair_expanded": repair_expanded,
    "peak_frontier": peak_frontier
}
```

Không sử dụng `extra` để thay thế các metric bắt buộc: `path`, `cost`, `expanded`.

---

## 6. Common Benchmark Metrics

Benchmark bắt buộc phải đo:

1. Execution Time
2. Memory Consumption
3. Expanded Nodes

### 6.1 Execution Time

Sử dụng `time.perf_counter()`:

```python
start_time = time.perf_counter()

result = solve(problem)

end_time = time.perf_counter()

time_ms = (end_time - start_time) * 1000
```

Đơn vị: **milliseconds (ms)**.

Không dùng `time.time()` cho benchmark chính nếu `perf_counter()` có thể sử dụng.

---

## 7. Memory Consumption

Memory phải được đo bằng `tracemalloc`:

```python
import tracemalloc

tracemalloc.start()

result = solve(problem)

current, peak = tracemalloc.get_traced_memory()

tracemalloc.stop()

memory_kb = peak / 1024
```

Metric chính: **Peak Memory (KB)**.

### 7.1 KHÔNG dùng Queue Size làm Memory

Không được:

```python
memory = len(queue)   # SAI nếu gọi đây là memory consumption
```

`peak_queue_size` có thể được lưu trong `extra`, nhưng phải gọi đúng tên `peak_frontier` hoặc `peak_queue_size`. Nó là **auxiliary metric**, không phải Memory Consumption.

---

## 8. Expanded Nodes

Metric bắt buộc: **Expanded Nodes**.

Định nghĩa:

> Number of nodes removed from the active search structure and processed by the algorithm.

**UCS**

```python
node = heapq.heappop(frontier)
expanded += 1
```

**A\***

```python
node = heapq.heappop(open_set)
expanded += 1
```

**IDA\***

Mỗi node được DFS/IDA* xử lý phải được tính theo cùng semantics.

**Bidirectional UCS**

```python
expanded = expanded_forward + expanded_backward
```

Có thể lưu thêm `expanded_forward`, `expanded_backward` trong `extra`.

**D\* Lite**

Có thể lưu `initial_expanded`, `repair_expanded` trong `extra`. Nhưng phải xác định rõ `expanded` là metric nào đang được báo cáo.

---

## 9. Correctness Requirements

Trước khi benchmark performance, phải kiểm tra correctness.

Một run chỉ được coi là **valid** nếu:

### 9.1 Path bắt đầu đúng

```python
path[0] == start
```

### 9.2 Path kết thúc đúng

```python
path[-1] == goal
```

### 9.3 Path hợp lệ

Mỗi cạnh `path[i] -> path[i+1]` phải tồn tại trong graph.

### 9.4 Cost chính xác

Tổng edge cost phải bằng `result["cost"]`.

Với floating point, dùng tolerance phù hợp: `math.isclose(...)`.

---

## 10. Optimality

Nếu baseline là optimal algorithm (UCS, A*) thì algorithm cải tiến phải trả về cùng optimal cost.

```python
assert ida_cost == baseline_cost
assert biucs_cost == baseline_cost
assert dstar_cost == baseline_cost
```

Với floating-point:

```python
math.isclose(new_cost, baseline_cost, rel_tol=1e-9)
```

Không được chỉ kiểm tra "algorithm finished" — phải kiểm tra **solution is correct**.

---

## 11. Failed Run

Nếu algorithm:

- crash;
- timeout;
- trả path sai;
- cost sai;
- không reconstruct được path;
- không thỏa correctness;

thì run phải được đánh dấu `status = FAILED`.

Không được đưa run lỗi vào bảng performance như một kết quả bình thường.

Không được tự ý thay `FAILED` thành `0` hoặc bỏ qua mà không ghi chú.

---

## 12. Common Test Case Structure

Tất cả thuật toán phải chạy trên cùng bộ test.

Mỗi test case nên có:

```python
{
    "test_id": "...",
    "category": "...",
    "graph": ...,
    "start": ...,
    "goal": ...,
    "edge_costs": ...,
    "description": "..."
}
```

Nếu graph được load từ file:

```python
problem = {
    "graph": graph,
    "start": start,
    "goal": goal
}
```

---

## 13. Test Categories

Bộ test chung gồm:

- `BASELINE`
- `BEST_CASE`
- `WORST_CASE`
- `DYNAMIC`
- `STRESS`

Không nhất thiết mọi algorithm phải có tất cả category nếu category đó không có ý nghĩa với algorithm.

---

## 14. BASELINE Case

`BASELINE` dùng để:

- kiểm tra correctness;
- kiểm tra algorithm trên dữ liệu chuẩn;
- so sánh với teacher baseline.

Ví dụ: Romania map.

Nếu sử dụng Romania map thì phải đảm bảo graph, edge costs, start, goal giống nhau giữa các thuật toán.

Không được:

```text
Algorithm A: Arad  -> Bucharest
Algorithm B: Sibiu -> Bucharest
```

nếu mục tiêu là so sánh performance.

---

## 15. BEST_CASE

`BEST_CASE` phải có **lý do cấu trúc**.

Không được gọi một test là `BEST_CASE` chỉ vì nó chạy nhanh.

Ví dụ hợp lệ:

- Start và Goal rất gần nhau.
- Bidirectional search gặp nhau gần giữa đường.
- IDA* tìm được solution ở threshold thấp.

Phải ghi explanation:

```python
"description": "Start and goal are close, resulting in a shallow search."
```

---

## 16. WORST_CASE

Tương tự `BEST_CASE`: phải có lý do tại sao case này gây khó khăn.

Ví dụ:

- large branching factor;
- deep solution;
- misleading heuristic;
- bidirectional search has little advantage.

Không được gọi `WORST_CASE` chỉ vì kết quả time lớn nhất sau khi chạy.

**Tên category phải mô tả đặc điểm của input, không phải kết quả đo.**

---

## 17. DYNAMIC Case

`DYNAMIC` chủ yếu dùng cho **A\* vs D\* Lite**.

Scenario:

```text
Initial environment
        ↓
Initial path
        ↓
Environment changes
        ↓
Replanning
```

D* Lite phải có khả năng reuse state từ previous search nếu implementation được yêu cầu là D* Lite.

A* baseline thường rerun search from scratch sau khi environment thay đổi.

Phải ghi rõ **initial planning** và **repair/replanning**. Không được trộn hai phase mà không giải thích.

---

## 18. A* vs D* Lite — Special Rules

**Đây là phần bắt buộc.**

A* và D* Lite phải dùng:

- same graph
- same start
- same goal
- same edge costs
- same heuristic

Ví dụ nếu `Start = Arad`, `Goal = Bucharest` thì cả hai phải dùng `Arad -> Bucharest`.

Không được dùng:

```text
A*:      Rimnicu Vilcea -> Bucharest
D* Lite: Arad -> Bucharest
```

### 18.1 A* Output

```python
{
    "path": path,
    "cost": cost,
    "expanded": expanded,
    "extra": {}
}
```

### 18.2 D* Lite Output

D* Lite cũng phải trả:

```python
{
    "path": path,
    "cost": cost,
    "expanded": expanded,
    "extra": {}
}
```

Không được chỉ trả `expanded` và queue size. D* Lite phải có thể kiểm tra `path`, `cost`, `correctness`.

### 18.3 D* Lite Memory

Không dùng `len(priority_queue)` làm memory.

Phải dùng `tracemalloc`. Queue size có thể lưu ở `extra["peak_queue_size"]`.

---

## 19. IDA* — Special Rules

IDA* phải giữ `f(n) = g(n) + h(n)` và iterative threshold.

Không được sử dụng một global visited set làm mất các path hợp lệ.

Có thể sử dụng path-based cycle detection:

```python
if node in current_path:
    continue
```

IDA* phải báo cáo `expanded` và có thể báo thêm `iterations`.

---

## 20. Bidirectional UCS — Special Rules

Bidirectional UCS phải sử dụng **forward search + backward search**.

Backward graph phải được xử lý đúng. Với directed graph, reverse edge phải được tạo chính xác.

Phải có stopping condition đảm bảo optimality.

Có thể báo:

```python
extra = {
    "expanded_forward": expanded_forward,
    "expanded_backward": expanded_backward
}
```

Tổng: `expanded = expanded_forward + expanded_backward`.

---

## 21. Benchmark Wrapper

Benchmark wrapper chung phải chịu trách nhiệm đo **time** và **memory**.

Không để từng algorithm tự định nghĩa cách đo khác nhau.

Pseudo-code:

```python
tracemalloc.start()

start_time = time.perf_counter()

result = solve(problem)

end_time = time.perf_counter()

current, peak = tracemalloc.get_traced_memory()

tracemalloc.stop()

time_ms = (end_time - start_time) * 1000
memory_kb = peak / 1024
```

---

## 22. Multiple Repetitions

Nếu benchmark yêu cầu nhiều repetitions:

```python
for i in range(repetitions):
    result = solve(problem)
```

Phải đảm bảo mỗi repetition là một execution độc lập. Không được để state của lần chạy trước ảnh hưởng sang lần chạy sau.

**Ngoại lệ:** D* Lite dynamic repair, vì việc giữ state là một phần bản chất của algorithm. Trong trường hợp đó phải ghi rõ **initial planning** và **repair**.

---

## 23. Benchmark Output

Benchmark cuối cùng nên có dạng:

| Test | Algorithm | Status | Cost | Expanded | Time (ms) | Memory (KB) |
|---|---|---|---|---|---|---|
| baseline_01 | IDA* | PASS | ... | ... | ... | ... |
| baseline_01 | Bi-UCS | PASS | ... | ... | ... | ... |
| baseline_01 | D* Lite | PASS | ... | ... | ... | ... |

Có thể bổ sung các cột: Iterations, Expanded Forward, Expanded Backward, Repair Expanded, Peak Queue Size.

Các metric này nằm trong `extra` và **không được thay thế metric chung**.

---

## 24. Không được làm

**AI CODING ASSISTANT KHÔNG ĐƯỢC:**

### 24.1 Không thay đổi test case chung

Không được tự ý sửa `start`, `goal`, `graph`, `edge cost`, `dynamic change` chỉ để algorithm chạy tốt hơn.

### 24.2 Không thay đổi metric

Không được đổi `expanded nodes` thành `generated nodes` mà không báo.

### 24.3 Không dùng queue size làm memory

```python
memory = len(queue)      # SAI
tracemalloc              # ĐÚNG
```

### 24.4 Không benchmark hai problem khác nhau

```text
SAI:
A*:      Arad -> Bucharest
D* Lite: Rimnicu Vilcea -> Bucharest
```

### 24.5 Không loại bỏ correctness check

Không được chỉ benchmark speed. Phải xác nhận: path correct, cost correct, optimality correct.

### 24.6 Không silently skip failure

Nếu algorithm fail: `status = FAILED` và phải ghi reason.

### 24.7 Không artificially cap search

Không được tự ý:

```python
if expanded > 10000:
    break
```

trừ khi specification của benchmark đã quy định timeout/limit.

### 24.8 Không tối ưu riêng cho test case

Không được hard-code:

```python
if start == "Arad" and goal == "Bucharest":
    ...
```

để làm algorithm chạy nhanh hơn.

### 24.9 Không đổi algorithm

Không được biến IDA* thành A*, hoặc D* Lite thành A*, chỉ để pass benchmark.

---

## 25. Correctness First, Performance Second

Thứ tự bắt buộc:

```text
1. Algorithm correctness
        ↓
2. Common interface
        ↓
3. Common metrics
        ↓
4. Benchmark
        ↓
5. Performance comparison
```

Không được tối ưu performance trước khi xác nhận correctness.

---

## 26. Required Self-Test

Sau khi sửa code, AI phải chạy ít nhất một test nhỏ.

```python
result = solve(problem)

print(result)
```

Phải xác nhận:

- path exists
- path starts at start
- path ends at goal
- cost is correct
- expanded >= 0

Nếu có baseline:

```python
assert result["cost"] == baseline_cost
```

hoặc:

```python
assert math.isclose(
    result["cost"],
    baseline_cost,
    rel_tol=1e-9
)
```

---

## 27. Required Final Response From AI

Sau khi sửa code, AI phải trả lời theo format:

**Files changed**

- filename.py

**Functions changed**

- solve()
- benchmark()
- reconstruct_path()

**What was changed**

Ví dụ:

1. Standardized `solve()` output.
2. Added expanded-node counting.
3. Added path reconstruction.
4. Removed queue size as memory metric.
5. Added `tracemalloc` measurement.

**Correctness**

`PASS / FAIL`

Explain:

- Returned path is valid.
- Returned cost matches path cost.

**Self-test**

Command: `python filename.py`

Expected: `PASS`

**Benchmark compatibility**

Confirm:

- [ ] Common `solve()` interface
- [ ] `path` returned
- [ ] `cost` returned
- [ ] `expanded` returned
- [ ] `extra` returned
- [ ] tracemalloc-compatible
- [ ] same test case compatible

---

## 28. Instructions for the AI Coding Assistant

Copy the following instruction together with this specification:

```text
You are modifying one algorithm implementation for the AI Midterm Project.

Read the entire BENCHMARK_SPEC.md before making any changes.

Your task is NOT to redesign the whole project.

Your task is to modify ONLY the assigned algorithm so that it follows the
common specification.

Requirements:

1. Preserve the algorithmic identity.
2. Do not replace the algorithm with another algorithm.
3. Implement:

   solve(problem) -> result

   with:

   result = {
       "path": path,
       "cost": cost,
       "expanded": expanded,
       "extra": extra
   }

4. Ensure path correctness.
5. Ensure returned cost equals path cost.
6. Ensure expanded-node counting follows the common definition.
7. Do not use queue size as memory.
8. The benchmark wrapper will measure:
   - execution time using time.perf_counter();
   - peak memory using tracemalloc.
9. Do not modify the common test cases.
10. Do not change start/goal/graph/edge costs to make your algorithm
    perform better.
11. Do not silently ignore failures.
12. Do not artificially cap the number of expanded nodes.
13. Add algorithm-specific metrics to extra if useful.
14. Make sure your implementation can be called by an external
    benchmark script.

Before finishing:

- Run a correctness test.
- Verify the returned path.
- Verify the returned cost.
- Verify expanded-node count.
- Explain every file/function you changed.
- Give the command needed to run the self-test.
- State whether the implementation is compatible with the common benchmark.

Do not modify another member's algorithm.
```

---

## 29. Algorithm-specific assignment

### Member: Dương Trung

**Assigned:** DFS → IDA*

**Main goal:** Make IDA* compatible with this benchmark specification.

Must provide: `path`, `cost`, `expanded`, `iterations`.

Optional: `peak_frontier`, threshold information.

### Member: Mint

**Assigned:** UCS → Bidirectional UCS

**Main goal:** Make Bidirectional UCS compatible with this benchmark specification.

Must provide: `path`, `cost`, `expanded`.

Optional: `expanded_forward`, `expanded_backward`, `peak_frontier`.

Must verify optimality against UCS.

### Member: Phương Anh

**Assigned:** A* → D* Lite

**Main goal:** Make D* Lite compatible with this benchmark specification.

Must provide: `path`, `cost`, `expanded`.

Must ensure:

- A* and D* Lite use the same problem.
- For dynamic tests, **initial planning**, **environment change**, and **repair/replanning** must be clearly separated.
- Do NOT use queue size = memory. Use `tracemalloc` for memory.

---

## 30. Integration Owner: Đức

After all three members finish their implementation, Đức will:

1. Collect the three implementations.
2. Check common interface.
3. Check correctness.
4. Run the same test suite.
5. Measure:
   - Time
   - Memory
   - Expanded Nodes
6. Verify baseline cost.
7. Identify meaningful best/worst cases.
8. Generate common benchmark tables.
9. Compare baseline vs improved algorithm.
10. Use the benchmark results to finalize the three A4 pages.

Đức should NOT manually modify another member's algorithm unless necessary for integration.

If an algorithm fails the common interface: **return to the responsible member** rather than silently changing benchmark definitions.

---

## 31. Final Benchmark Philosophy

The goal is NOT:

> Make the improved algorithm produce the smallest possible benchmark number.

The goal is:

> Produce a fair, reproducible, correctness-verified comparison between the baseline and improved algorithm.

Therefore:

```text
Correctness
    >
Common Interface
    >
Fair Benchmark
    >
Performance Analysis
```

- A faster algorithm with an incorrect path is NOT considered better.
- A lower memory number obtained using a different memory definition is NOT considered better.
- A benchmark result obtained from a different graph/start/goal is NOT considered comparable.

The final comparison must be:

```text
Same Problem
+ Same Conditions
+ Same Metrics
+ Correct Solutions
= Fair Comparison
```

---

## 32. Quy trình sử dụng (Workflow)

```text
BENCHMARK_SPEC.md
        │
        ├──→ AI của Dương Trung ── sửa IDA*
        │
        ├──→ AI của Mint ───────── sửa Bidirectional UCS
        │
        └──→ AI của Phương Anh ─── sửa D* Lite
                         ↓
                  Đức nhận code
                         ↓
              Common Benchmark Script
         