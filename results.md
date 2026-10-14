| Test | Category | Algorithm | Status | Cost | Expanded | Iterations | Peak frontier | Time (ms) | Memory (KB) |
|---|---|---|---|---|---|---|---|---|---|
| baseline_romania_arad_bucharest | BASELINE | DFS | PASS | 1335.80 | 9 | 1 | 10 | 0.025 | 3.4 |
| baseline_romania_arad_bucharest | BASELINE | IDA* | PASS | 657.85 | 63 | 11 | 4 | 0.213 | 3.6 |
| baseline_romania_arad_bucharest | BASELINE | A* (ref) | PASS | 657.85 | 11 | 1 | 6 | 0.034 | 2.8 |
| baseline_romania_oradea_giurgiu | BASELINE | DFS | PASS | 1387.46 | 14 | 1 | 12 | 0.042 | 3.7 |
| baseline_romania_oradea_giurgiu | BASELINE | IDA* | PASS | 975.56 | 153 | 17 | 6 | 0.531 | 4.7 |
| baseline_romania_oradea_giurgiu | BASELINE | A* (ref) | PASS | 975.56 | 12 | 1 | 5 | 0.034 | 2.9 |
| baseline_romania_iasi_craiova | BASELINE | DFS | PASS | 1707.88 | 11 | 1 | 9 | 0.023 | 3.2 |
| baseline_romania_iasi_craiova | BASELINE | IDA* | PASS | 962.69 | 42 | 9 | 5 | 0.149 | 4.4 |
| baseline_romania_iasi_craiova | BASELINE | A* (ref) | PASS | 962.69 | 9 | 1 | 5 | 0.032 | 2.4 |
| baseline_romania_blocked_edge | BASELINE | DFS | PASS | 1930.98 | 12 | 1 | 10 | 0.037 | 3.5 |
| baseline_romania_blocked_edge | BASELINE | IDA* | PASS | 785.71 | 61 | 11 | 4 | 0.247 | 3.4 |
| baseline_romania_blocked_edge | BASELINE | A* (ref) | PASS | 785.71 | 11 | 1 | 5 | 0.042 | 2.6 |
| best_romania_adjacent_dry | BEST_CASE | DFS | PASS | 676.00 | 13 | 1 | 11 | 0.043 | 3.7 |
| best_romania_adjacent_dry | BEST_CASE | IDA* | PASS | 99.00 | 3 | 2 | 1 | 0.012 | 1.7 |
| best_romania_adjacent_dry | BEST_CASE | A* (ref) | PASS | 99.00 | 2 | 1 | 4 | 0.009 | 1.3 |
| best_corridor_100_dry | BEST_CASE | DFS | PASS | 990.00 | 100 | 1 | 198 | 0.358 | 44.3 |
| best_corridor_100_dry | BEST_CASE | IDA* | PASS | 990.00 | 100 | 1 | 99 | 0.434 | 62.7 |
| best_corridor_100_dry | BEST_CASE | A* (ref) | PASS | 990.00 | 100 | 1 | 100 | 0.397 | 35.3 |
| worst_grid4x4_continuous_flood | WORST_CASE | DFS | PASS | 104.93 | 7 | 1 | 11 | 0.023 | 3.3 |
| worst_grid4x4_continuous_flood | WORST_CASE | IDA* | PASS | 85.43 | 478 | 31 | 6 | 1.639 | 4.9 |
| worst_grid4x4_continuous_flood | WORST_CASE | A* (ref) | PASS | 85.43 | 16 | 1 | 6 | 0.060 | 3.1 |
| worst_grid5x5_continuous_flood | WORST_CASE | DFS | PASS | 127.60 | 9 | 1 | 15 | 0.023 | 3.9 |
| worst_grid5x5_continuous_flood | WORST_CASE | IDA* | PASS | 102.53 | 1398 | 53 | 8 | 4.791 | 6.0 |
| worst_grid5x5_continuous_flood | WORST_CASE | A* (ref) | PASS | 102.53 | 22 | 1 | 8 | 0.216 | 4.5 |
| worst_grid6x6_continuous_flood | WORST_CASE | DFS | PASS | 155.83 | 11 | 1 | 19 | 0.031 | 4.4 |
| worst_grid6x6_continuous_flood | WORST_CASE | IDA* | PASS | 152.67 | 85552 | 412 | 10 | 314.005 | 7.6 |
| worst_grid6x6_continuous_flood | WORST_CASE | A* (ref) | PASS | 152.67 | 36 | 1 | 10 | 0.141 | 5.2 |
| worst_grid7x7_continuous_flood | WORST_CASE | DFS | PASS | 190.50 | 13 | 1 | 23 | 0.036 | 5.0 |
| worst_grid7x7_continuous_flood | WORST_CASE | IDA* | PASS | 182.07 | 460482 | 952 | 12 | 2047.808 | 8.8 |
| worst_grid7x7_continuous_flood | WORST_CASE | A* (ref) | PASS | 182.07 | 49 | 1 | 13 | 0.179 | 7.4 |
| worst_grid8x8_continuous_flood | WORST_CASE | DFS | PASS | 246.90 | 15 | 1 | 27 | 0.072 | 5.6 |
| worst_grid8x8_continuous_flood | WORST_CASE | IDA* | PASS | 204.93 | 2417004 | 2168 | 15 | 10453.162 | 10.0 |
| worst_grid8x8_continuous_flood | WORST_CASE | A* (ref) | PASS | 204.93 | 63 | 1 | 14 | 0.169 | 8.5 |
| stress_grid6x6_dry_flood | STRESS | DFS | PASS | 100.00 | 11 | 1 | 19 | 0.025 | 4.4 |
| stress_grid6x6_dry_flood | STRESS | IDA* | PASS | 100.00 | 1623 | 19 | 10 | 4.830 | 7.1 |
| stress_grid6x6_dry_flood | STRESS | A* (ref) | PASS | 100.00 | 36 | 1 | 10 | 0.114 | 5.5 |
| stress_grid6x6_quantized_flood | STRESS | DFS | PASS | 145.00 | 11 | 1 | 19 | 0.023 | 4.4 |
| stress_grid6x6_quantized_flood | STRESS | IDA* | PASS | 140.00 | 11242 | 91 | 11 | 31.322 | 7.9 |
| stress_grid6x6_quantized_flood | STRESS | A* (ref) | PASS | 140.00 | 36 | 1 | 10 | 0.106 | 5.3 |
| stress_grid7x7_dry_flood | STRESS | DFS | PASS | 120.00 | 13 | 1 | 23 | 0.028 | 5.0 |
| stress_grid7x7_dry_flood | STRESS | IDA* | PASS | 120.00 | 8303 | 29 | 12 | 24.831 | 8.1 |
| stress_grid7x7_dry_flood | STRESS | A* (ref) | PASS | 120.00 | 49 | 1 | 12 | 0.132 | 8.2 |
| stress_grid7x7_quantized_flood | STRESS | DFS | PASS | 195.00 | 13 | 1 | 23 | 0.031 | 5.0 |
| stress_grid7x7_quantized_flood | STRESS | IDA* | PASS | 145.00 | 11284 | 104 | 12 | 32.893 | 8.6 |
| stress_grid7x7_quantized_flood | STRESS | A* (ref) | PASS | 145.00 | 41 | 1 | 13 | 0.208 | 7.9 |
| stress_grid8x8_dry_flood | STRESS | DFS | PASS | 140.00 | 15 | 1 | 27 | 0.062 | 5.6 |
| stress_grid8x8_dry_flood | STRESS | IDA* | PASS | 140.00 | 37688 | 40 | 14 | 164.319 | 9.2 |
| stress_grid8x8_dry_flood | STRESS | A* (ref) | PASS | 140.00 | 64 | 1 | 14 | 0.236 | 9.2 |
| stress_grid9x9_dry_flood | STRESS | DFS | PASS | 160.00 | 17 | 1 | 31 | 0.051 | 6.3 |
| stress_grid9x9_dry_flood | STRESS | IDA* | PASS | 160.00 | 194826 | 54 | 16 | 970.018 | 10.4 |
| stress_grid9x9_dry_flood | STRESS | A* (ref) | PASS | 160.00 | 81 | 1 | 16 | 0.386 | 10.8 |
| stress_grid10x10_dry_flood | STRESS | DFS | PASS | 180.00 | 19 | 1 | 35 | 0.072 | 6.9 |
| stress_grid10x10_dry_flood | STRESS | IDA* | PASS | 180.00 | 991907 | 73 | 18 | 4506.089 | 12.4 |
| stress_grid10x10_dry_flood | STRESS | A* (ref) | PASS | 180.00 | 100 | 1 | 18 | 0.296 | 15.7 |
| stress_grid8x8_quantized_flood | STRESS | DFS | PASS | 205.00 | 15 | 1 | 27 | 0.039 | 5.6 |
| stress_grid8x8_quantized_flood | STRESS | IDA* | PASS | 180.00 | 86860 | 210 | 14 | 313.166 | 9.9 |
| stress_grid8x8_quantized_flood | STRESS | A* (ref) | PASS | 180.00 | 61 | 1 | 17 | 0.256 | 8.5 |
