// Chart.js rendering helpers for the PropRadar dashboard.
// Exposes global `PropRadarCharts` with render helpers; instances are tracked so
// they can be destroyed when switching platform tabs.

const PropRadarCharts = (() => {
  const instances = {};
  const COLORS = {
    accent: "#2f81f7",
    win: "#2ea043",
    loss: "#f85149",
    grid: "rgba(139, 149, 165, 0.12)",
    text: "#8b95a5",
  };

  function destroy(key) {
    if (instances[key]) {
      instances[key].destroy();
      delete instances[key];
    }
  }

  function baseOptions(extra = {}) {
    return Object.assign(
      {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: COLORS.grid }, ticks: { color: COLORS.text, maxRotation: 0, autoSkip: true } },
          y: { grid: { color: COLORS.grid }, ticks: { color: COLORS.text } },
        },
      },
      extra
    );
  }

  function renderProfit(canvas, series) {
    destroy("profit");
    if (!series || !series.length) return;
    const labels = series.map((p) => p.date);
    const data = series.map((p) => p.cumulative);
    const lastPositive = data.length && data[data.length - 1] >= 0;
    const line = lastPositive ? COLORS.win : COLORS.loss;
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 300);
    gradient.addColorStop(0, lastPositive ? "rgba(46,160,67,0.30)" : "rgba(248,81,73,0.30)");
    gradient.addColorStop(1, "rgba(0,0,0,0)");

    instances.profit = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            data,
            borderColor: line,
            backgroundColor: gradient,
            fill: true,
            tension: 0.25,
            pointRadius: 0,
            borderWidth: 2,
          },
        ],
      },
      options: baseOptions(),
    });
  }

  function renderBreakdown(canvas, rows) {
    destroy("breakdown");
    if (!rows || !rows.length) return;
    const labels = rows.map((r) => r.key);
    const data = rows.map((r) => r.hit_rate);
    instances.breakdown = new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            data,
            backgroundColor: data.map((v) =>
              v == null ? COLORS.text : v >= 50 ? COLORS.win : COLORS.loss
            ),
            borderRadius: 6,
          },
        ],
      },
      options: baseOptions({
        scales: {
          x: { grid: { color: COLORS.grid }, ticks: { color: COLORS.text } },
          y: { grid: { color: COLORS.grid }, ticks: { color: COLORS.text }, min: 0, max: 100 },
        },
      }),
    });
  }

  function destroyAll() {
    Object.keys(instances).forEach(destroy);
  }

  return { renderProfit, renderBreakdown, destroyAll };
})();
