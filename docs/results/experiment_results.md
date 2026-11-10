# Experiment results (measured)

Generated 2026-11-10T07:30:27 with Eclipse SUMO sumo 1.28.0. Duration 1800 s, seeds [1, 2, 3]. Values are the mean over seeds (± standard deviation).


## Scenario: low (batch `low_faa7e1`)

| Controller | Avg waiting (s) | Avg travel (s) | Mean queue/lane | Max lane queue | Throughput | Stops/veh | Phase changes | Latency ms | Starvation |
|---|---|---|---|---|---|---|---|---|---|
| Fixed-Time | 50.34 ± 1.90 | 127.59 ± 2.99 | 0.34 ± 0.03 | 7.67 ± 0.47 | 558.67 ± 40.67 | 1.41 ± 0.05 | 272.00 | 0.0031 ± 0.0001 | 0.00 |
| Adaptive (VAC) | 21.85 ± 1.84 | 99.35 ± 2.80 | 0.15 ± 0.02 | 4.33 ± 0.47 | 569.67 ± 39.94 | 1.42 ± 0.04 | 468.67 ± 2.05 | 0.0059 ± 0.0001 | 0.00 |
| Max-Pressure | 33.16 ± 0.14 | 111.67 ± 0.98 | 0.23 ± 0.01 | 5.00 ± 0.82 | 565.00 ± 41.14 | 1.70 ± 0.06 | 394.67 ± 21.64 | 0.0045 ± 0.0002 | 2.00 |

Change vs Fixed-Time (negative = lower value):

| Controller | Avg waiting | Avg travel | Mean queue | Throughput | Stops/veh |
|---|---|---|---|---|---|
| Adaptive (VAC) | -56.59% | -22.14% | -56.39% | 1.97% | 0.59% |
| Max-Pressure | -34.12% | -12.48% | -34.1% | 1.13% | 20.35% |

## Scenario: medium (batch `medium_9977c4`)

| Controller | Avg waiting (s) | Avg travel (s) | Mean queue/lane | Max lane queue | Throughput | Stops/veh | Phase changes | Latency ms | Starvation |
|---|---|---|---|---|---|---|---|---|---|
| Fixed-Time | 61.55 ± 3.42 | 141.62 ± 3.42 | 0.83 ± 0.07 | 10.67 ± 0.94 | 1115.33 ± 37.82 | 1.61 ± 0.03 | 272.00 | 0.0031 ± 0.0001 | 0.00 |
| Adaptive (VAC) | 36.42 ± 0.57 | 115.53 ± 1.08 | 0.49 ± 0.01 | 8.33 ± 0.47 | 1125.67 ± 39.23 | 1.53 ± 0.03 | 401.67 ± 5.19 | 0.0063 ± 0.0001 | 0.00 |
| Max-Pressure | 41.73 ± 1.79 | 123.09 ± 1.76 | 0.57 ± 0.04 | 7.33 ± 0.94 | 1123.00 ± 35.52 | 2.00 ± 0.03 | 504.33 ± 4.50 | 0.0044 ± 0.0001 | 3.33 ± 1.25 |

Change vs Fixed-Time (negative = lower value):

| Controller | Avg waiting | Avg travel | Mean queue | Throughput | Stops/veh |
|---|---|---|---|---|---|
| Adaptive (VAC) | -40.84% | -18.42% | -40.71% | 0.93% | -4.85% |
| Max-Pressure | -32.21% | -13.09% | -32.14% | 0.69% | 24.41% |

## Scenario: high (batch `high_647758`)

| Controller | Avg waiting (s) | Avg travel (s) | Mean queue/lane | Max lane queue | Throughput | Stops/veh | Phase changes | Latency ms | Starvation |
|---|---|---|---|---|---|---|---|---|---|
| Fixed-Time | 87.78 ± 5.39 | 171.18 ± 6.36 | 1.92 ± 0.17 | 30.00 ± 2.45 | 1568.67 ± 28.89 | 1.92 ± 0.07 | 272.00 | 0.0032 ± 0.0002 | 0.00 |
| Adaptive (VAC) | 55.01 ± 2.67 | 136.28 ± 3.09 | 1.13 ± 0.07 | 14.67 ± 1.70 | 1659.67 ± 19.36 | 1.69 ± 0.01 | 311.67 ± 7.36 | 0.0064 | 0.00 |
| Max-Pressure | 72.84 ± 2.92 | 161.07 ± 3.13 | 1.51 ± 0.06 | 16.67 ± 1.25 | 1610.00 ± 28.25 | 2.88 ± 0.02 | 530.67 ± 4.50 | 0.0041 | 7.67 ± 1.70 |

Change vs Fixed-Time (negative = lower value):

| Controller | Avg waiting | Avg travel | Mean queue | Throughput | Stops/veh |
|---|---|---|---|---|---|
| Adaptive (VAC) | -37.34% | -20.39% | -41.39% | 5.8% | -12.17% |
| Max-Pressure | -17.02% | -5.91% | -21.28% | 2.63% | 50.11% |
