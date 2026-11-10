# User Guide

Start the backend and the dashboard as described in [HOW_TO_RUN.md](../HOW_TO_RUN.md), then open
http://localhost:8501. The **sidebar** always shows whether the backend is online, whether SUMO is
ready, and the live simulation status.

## A. Home Dashboard
Headline numbers for the running simulation: total vehicles, average waiting time, average queue
per lane, throughput, traffic condition (Free / Moderate / Heavy / Severe), active intersections,
the controller running and phase changes. It refreshes every 2 s. A table shows each junction's
current phase, mode and most congested approach. The latest 5 stored experiments are listed at
the bottom. If nothing is running, the page says so; it never shows invented numbers.

## B. Live Simulation
1. Choose **Traffic scenario** (low/medium/high), **Controller**, **Random seed**, **Duration** and
   **Speed** (simulated seconds per real second).
2. Optionally tick **Open sumo-gui** to also see SUMO's own window on the same computer.
3. Press **Start**. The map updates every second:
   * dots = vehicles (lighter = slower, darker blue = faster; hover for id, type and speed);
   * squares at stop lines = signal of each lane (green / amber / red);
   * labels = junction, current phase, mode and green time.
4. **Pause** freezes the simulation, **Resume** continues, **Reset** stops and discards it,
   **Apply speed** changes the speed while running.
5. When the run reaches its duration it is saved automatically, and a message shows the experiment number.

## C. Traffic Monitoring
* Cards: the **busiest lane** (its junction, approach, score, queue, waiting), network congestion,
  number of monitored lanes.
* Choose **All** or one junction.
* Bar chart: the most congested lanes, coloured by level (hover for details).
* Heat map: mean congestion per approach (N/E/S/W) for each junction.
* Lane table: vehicles, queue, occupancy, speed, average wait, arrivals/min, congestion score,
  queue pressure and level for all 48 lanes.

## D. Adaptive Control
Choose a junction to see:
* the **selected phase**, the **signal mode** (GREEN / YELLOW / ALL_RED), the **green time** and the controller;
* **Why this decision**: the controller's own explanation (for example EXTEND, GAP_OUT, MAX_OUT, STARVATION);
* bar charts of **demand**, **max-pressure** and **queue** per phase (the highlighted bar is being served);
* how long each phase's vehicles have waited on red;
* the **decision log** and the **signal transitions** (green → amber → all-red → green with state strings).

This page works for every controller, so you can see how Fixed-Time or Max-Pressure decide too.

## E. Controller Comparison
1. Choose scenario, controllers, seeds (e.g. `1,2,3`) and duration, then press **Run comparison**.
2. A progress bar shows which run is executing. For every seed, all controllers get identical traffic.
3. When it finishes, you see 9 bar charts (mean ± standard deviation across seeds), a results table
   and the **% change vs Fixed-Time**, with a "better/worse on this data" verdict.
4. Earlier batches can be selected from the **Comparison batch** list.

Use at least 3 seeds before you claim that one controller is better.

## F. Analytics
* **Stored experiments**: pick any experiments. You get interactive line charts of average waiting
  time, queue length, throughput, average speed, congestion, phase changes and controller computation time.
* **Current live run**: the same charts for the simulation in progress.
* Colour = controller; line style separates runs of the same controller. Hover to compare values at
  the same time; drag to zoom; double-click to reset.

## G. Reports
* Filter the history by scenario, controller or batch.
* **Download CSV**: all columns for the filtered experiments.
* **Generate PDF report** then **Download PDF**: summary table, metric comparison charts, time series.
* **Delete an experiment** from the expander.

## Tips for a demonstration
1. Run a comparison on **high** demand with seeds `1,2,3` before the presentation (about 2 minutes).
2. During the demo, start a **live** high-demand Adaptive run at speed 10. Show the map, then
   Adaptive Control (the reasons), then Monitoring.
3. Then show Controller Comparison and Analytics for the batch you ran, and download the PDF.
