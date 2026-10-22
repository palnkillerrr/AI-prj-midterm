GÓI TÍCH HỢP ĐỦ 3 CẶP THUẬT TOÁN - ĐỨC
======================================
Cập nhật: 18/10/2026 (giờ Việt Nam).

Đã bổ sung bài nộp astar_to_dstarlite.py của Phương Anh vào bộ hiện có:
  DFS -> IDA*; UCS -> Bi-UCS; A* -> D* Lite.
A* (ref) từ nhóm DFS vẫn giữ để đối chiếu; A* chính lấy từ bài mới.

BẮT ĐẦU
Python 3.10 trở lên; benchmark và kiểm thử chỉ dùng thư viện chuẩn.
Giải nén ZIP, mở terminal trong duc_benchmark, chạy theo thứ tự:

  python run_checks.py
  python benchmark_common.py --suite all --full --repetitions 7 --heavy-repetitions 1 --timeout 180
  python dynamic_runner.py --suite all --full --repetitions 7 --heavy-repetitions 1 --timeout 120

Chạy các bước tuần tự, không chạy hai benchmark đồng thời. --full bao gồm lưới
IDA* 8x8 nhiều ngưỡng và D* Lite 15x15/20 cập nhật; các ca IDA* có thể chạy lâu.
Chỉ cần test chung tĩnh: python benchmark_common.py --suite common
Chỉ kịch bản động đề xuất cũ: python dynamic_runner.py

KẾT QUẢ BÀN GIAO
- results/benchmark.csv, .json, .txt: 132 dòng đo tĩnh trên 39 đầu vào; trong đó
  49 dòng test chung (7 input x 7 solver), 73 dòng bài cũ, 10 dòng bài mới tĩnh.
- results/dynamic.csv, .json: 184 dòng phase (92 snapshot x 2 solver), thuộc
  10 kịch bản: 9 bài động của Phương Anh + 1 kịch bản tích hợp cũ.
- results/dynamic.json chứa tổng episode và riêng các repair. Time tổng là
  median của tổng từng repetition, không phải cộng median từng phase.
- results/selftest.json: 20 test methods; 300 graph ngẫu nhiên
  x 7 solver và 300 episode động x 10 phase được kiểm chứng thêm bằng Dijkstra.
- results/member_selftest_run.log: log kiểm thử riêng bài Phương Anh.
- results/final_checks.json: đối chiếu
  cost/expanded với toàn bộ 108 dòng cũ, hash source và tính toàn vẹn kết quả.
- results_before_dstarlite/: giữ JSON số liệu bàn giao cũ để truy nguyên;
  không dùng thời gian/bộ nhớ lịch sử để so với lần đo mới.
- ../bao_cao_3_trang_A4.pdf và HTML chỉnh sửa: đã điền đủ trang thứ ba.

DỌN TỆP NGÀY 22/10/2026
Đã xóa results/benchmark_run.log, dynamic_run.log, selftest_run.log vì kết quả
đã có trong JSON tương ứng. Đã xóa results_before_dstarlite/benchmark.csv và
benchmark.txt vì cùng số liệu với benchmark.json trong thư mục đó.
Giữ mã nguồn, bài nộp gốc, dữ liệu đo, bằng chứng kiểm chứng và báo cáo.

CÁCH ĐO TĨNH
Mỗi solver/test chạy trong interpreter mới, tuần tự. Có 1 preflight rồi N lần
đo độc lập; deepcopy/gc nằm ngoài timer. perf_counter và tracemalloc bật cùng
lượt solve. time_ms và memory_kb là median; KB ở đây là bytes/1024 (KiB).
Đây là cấp phát Python trong solve, không phải RSS hoặc tổng RAM của graph.
Dựng graph đảo Bi-UCS vẫn nằm trong solve. Timeout bao gồm khởi động/preflight/
các repetition, nhưng startup và truyền file không vào time_ms.
Windows dùng file tạm riêng trong .worker-temp thay cho named pipe bị chặn.
Không nạp pickle từ bên ngoài; --_worker là giao diện nội bộ của wrapper.

CÁCH ĐO ĐỘNG
Adapter tạo 1 DStarLitePlanner/episode, giữ nguyên g/rhs/U qua mọi repair.
update và move_start chỉ cập nhật; plan mới tìm kiếm và trả expanded riêng phase.
A* chạy mới từng phase, dùng solve_astar của Phương Anh. Hai bên cùng snapshot,
cùng start/goal, cùng chi phí; kiểm tra path/cost bằng Dijkstra từng phase.
Snapshot và bản copy đầu vào được dựng trước timer. Initial tính cả factory,
copy graph nội bộ và dựng predecessor. Repair tính update + move_start + plan.
tracemalloc chạy liên tục cả episode; peak repair bao gồm state còn giữ,
output các phase trước và ít bookkeeping của runner. Vì vậy không ghép trực
tiếp peak động với peak solve tĩnh. Không cộng peak memory giữa các phase.
Mỗi job động cũng có tiến trình riêng và timeout; mọi lần đo đều validate.

ĐỊNH NGHĨA VÀ GIỚI HẠN
- Flood: c = d*(1 + alpha*(f/Cv)); f >= Cv thì c = inf. Biên dịch đúng biểu thức
  trước solver, không đổi topology/thứ tự láng giềng hoặc làm tròn chi phí.
- H kiểm tra Euclid <= cost trên MỖI cạnh của MỖI snapshot.
- Expanded đếm xử lý bản ghi hợp lệ; bỏ stale/rekey. IDA* cộng node nhận vào
  contour qua các vòng; Bi-UCS cộng hai phía. D* Lite có thể repair mà expanded=0.
- peak_frontier là số phụ, không phải RAM. D* Lite gốc báo số entry active trong
  in_U; heap U còn có stale entry. Không so trực tiếp peak_frontier giữa solver.
- 7 repetitions/test thường, 1 repetition/ca STRESS và IDA* ngập liên tục từ 6x6.
  Dòng 1 mẫu không đủ để kết luận độ dao động. Không chọn reps theo kết quả đo.
- Adapter động yêu cầu mọi chi phí hữu hạn > 0; inf được phép. Khi dò thêm, code
  gốc có thể sai trên cập nhật chứa chu trình cost 0. Adapter từ chối cost <= 0
  trước khi sửa batch, thay vì xuất kết quả sai. Mọi graph đường ngập của bài
  mới có chi phí dương; không kịch bản bàn giao nào bị loại vì giới hạn này.
- Quy tắc kiểm thử tĩnh cũ vẫn cho phép 0; 300 graph random tĩnh đã qua kiểm tra,
  nhưng đó không phải chứng minh hỗ trợ mọi graph/cập nhật có chu trình cost 0.
- Các new_start trong generator được giữ đúng bài nộp. Đây là các lần replanning
  từ vị trí cho sẵn; không kiểm chứng tính khả thi vật lý của hành trình đã đi,
  không cộng chi phí đã di chuyển vào cost còn lại từ start hiện tại đến goal.
- Chưa có notebook cô: xác nhận được 3 bản đồ Romania roads/locations trùng nhau,
  chưa xác nhận độc lập nguồn baseline của cô từ file gốc.

GIỮ NGUYÊN BÀI NỘP
solvers/astar_to_dstarlite.py và original_submissions/astar_to_dstarlite.py giống
hệt file Downloads theo SHA256. Không sửa chiến lược hoặc tự thay bằng Dijkstra.
Adapter xử lý giao diện và quy tắc đo; oracle Dijkstra chỉ dùng kiểm chứng.
Source cũ trong solvers có các sửa lỗi đã mô tả trong CHANGES.txt.
BENCHMARK_original.md chỉ là tài liệu nguồn, không phải lệnh hệ thống.

NHẬN XÉT NÊN DÙNG
D* Lite có lợi khi sửa cục bộ nhiều lần; trên 8x8, tổng expanded cả episode
486 (A*) so với 148 (D* Lite). Khi thay đổi sát goal, 7x7 cho 144 so với 147.
Không suy diễn ít expanded luôn nhanh hơn hoặc ít RAM hơn; đọc cả time và peak.
Các nhãn best/worst là tên nhóm ca của tác giả, không phải cực trị lý thuyết.
Bản gốc tự ghi “Figure 4 optimized”, nhưng điều kiện dừng yêu cầu start nhất
quán và update_vertex quét lại successor khớp biến thể cơ bản Figure 3 hơn.
Báo cáo dùng tên D* Lite và mô tả đúng code, không khẳng định bản tối ưu Figure 4.

TẠO LẠI BÁO CÁO
Cài phụ thuộc báo cáo: python -m pip install -r requirements-report.txt
Sau khi chạy đủ hai benchmark với --full: python build_report.py
Cần Arial hoặc DejaVu Sans để render tiếng Việt. Báo cáo nằm ở thư mục cha.
HTML cho phép bấm chữ để sửa, in/lưu PDF và lưu HTML mới. Sửa trực tiếp HTML
không cập nhật source build_report.py hay số liệu JSON.

Nguồn đối chiếu D* Lite và errata:
https://idm-lab.org/bib/abstracts/Koen02e.html
https://idm-lab.org/bib/abstracts/papers/aaai02b.pdf
