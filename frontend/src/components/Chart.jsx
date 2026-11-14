import { useEffect, useRef, useState } from "react";

const PALETTE = {
  light: ["#2c4fa3", "#176b4d", "#a8321e", "#8a5a00", "#6b4fa0", "#2a7f8f"],
  dark: ["#7da2ff", "#5fd0a2", "#ff9a85", "#f0be5b", "#b79cf0", "#6fd0e0"],
};

export default function Chart({ chart, theme = "light" }) {
  const ref = useRef(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let plotly;
    let cancelled = false;
    const COLORS = PALETTE[theme] ?? PALETTE.light;
    const css = getComputedStyle(document.documentElement);
    const ink = css.getPropertyValue("--ink").trim() || "#1c2433";
    const rule = css.getPropertyValue("--rule").trim() || "#d6dbd2";
    const axis = (a) => ({ ...a, gridcolor: rule, linecolor: rule, zerolinecolor: rule });
    import("plotly.js-dist-min")
      .then((m) => {
        if (cancelled || !ref.current) return;
        plotly = m.default ?? m;
        const fig = chart.figure;
        plotly.newPlot(
          ref.current,
          fig.data.map((t, i) => ({
            ...t,
            marker: { ...t.marker, color: COLORS[i % COLORS.length] },
            ...(t.line ? { line: { ...t.line, color: COLORS[i % COLORS.length] } } : {}),
          })),
          {
            ...fig.layout,
            template: undefined,
            colorway: COLORS,
            autosize: true,
            height: 340,
            margin: { l: 64, r: 16, t: 24, b: 56 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            xaxis: { ...axis(fig.layout.xaxis), showgrid: false },
            yaxis: axis(fig.layout.yaxis),
            font: { family: "Schibsted Grotesk, system-ui, sans-serif", size: 13, color: ink },
          },
          { responsive: true, displaylogo: false },
        );
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (plotly && ref.current) plotly.purge(ref.current);
    };
  }, [chart, theme]);

  return (
    <figure className="chart">
      {failed ? <p className="notice">The chart could not be drawn in this browser.</p> : <div ref={ref} />}
      <figcaption className="chart__caption">
        {chart.kind} chart of {chart.y ? `${chart.y} by ${chart.x}` : chart.x}
      </figcaption>
    </figure>
  );
}
