import { useId, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import type { TimeSeriesPoint } from "../types/backtest";

export interface ChartSeries {
  label: string;
  points: TimeSeriesPoint[];
  color: string;
  dashed?: boolean;
  area?: boolean;
  valueFormat: (value: number) => string;
}

function slugify(label: string) {
  return label.replace(/[^a-zA-Z0-9]+/g, "-");
}

export function AxisCurve({ title, series, valueFormat, includeZero = false }: { title: string; series: ChartSeries[]; valueFormat: (value: number) => string; includeZero?: boolean }) {
  const prepared = useMemo(() => prepareSeries(series, includeZero), [includeZero, series]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hover, setHover] = useState<{ index: number; x: number } | null>(null);
  const gradientId = useId();

  function handleMove(event: ReactMouseEvent<SVGRectElement>) {
    const rect = containerRef.current?.getBoundingClientRect();
    const svgRect = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
    if (!rect || !svgRect) return;
    // Use the SVG's rect instead of the scroll container's width so hover
    // remains aligned when the mobile chart is horizontally scrolled.
    const relativeX = ((event.clientX - svgRect.left) / svgRect.width) * 880;
    const length = prepared.pointCount;
    const rawIndex = ((relativeX - 70) / 780) * (length - 1);
    const index = Math.min(length - 1, Math.max(0, Math.round(rawIndex)));
    setHover({ index, x: event.clientX - rect.left });
  }

  const hoverRows = hover
    ? prepared.paths.map((path, seriesIndex) => ({
        label: path.label,
        color: path.color,
        value: series[seriesIndex]?.valueFormat(prepared.seriesValues[seriesIndex]?.[hover.index] ?? 0) ?? ""
      }))
    : [];
  const hoverDate = hover ? prepared.dates[hover.index] ?? "" : "";
  const hoverPlotX = hover ? xForIndex(hover.index, prepared.pointCount) : 0;

  return (
    <section className="chartPanel">
      <div className="panelHeader compact">
        <div>
          <h3>{title}</h3>
          <p>{prepared.startDate} to {prepared.endDate}</p>
        </div>
        <span className="badge">{valueFormat(prepared.latestValue)}</span>
      </div>
      <div className="chartLegend">
        {series.map((item) => (
          <span key={item.label}><i style={{ background: item.color }} />{item.label}: {item.valueFormat(lastPoint(item.points)?.value ?? 0)}</span>
        ))}
      </div>
      <div className="chartCanvas" ref={containerRef}>
        <svg className="axisChart" viewBox="0 0 880 320" role="img" aria-label={title} preserveAspectRatio="none">
          <defs>
            {prepared.paths.filter((path) => path.area).map((path) => (
              <linearGradient id={`${gradientId}-${slugify(path.label)}`} key={path.label} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={path.color} stopOpacity="0.04" />
                <stop offset="100%" stopColor={path.color} stopOpacity="0.4" />
              </linearGradient>
            ))}
          </defs>
          {prepared.yTicks.map((tick) => (
            <g key={tick.value}>
              <line className="gridLine" x1="70" x2="850" y1={tick.y} y2={tick.y} />
              <text className="axisText" x="62" y={tick.y + 4} textAnchor="end">{valueFormat(tick.value)}</text>
            </g>
          ))}
          {prepared.xTicks.map((tick) => (
            <g key={tick.x}>
              <line className="gridLine vertical" x1={tick.x} x2={tick.x} y1="24" y2="280" />
              <text className="axisText" x={tick.x} y="300" textAnchor="middle">{tick.date}</text>
            </g>
          ))}
          <line className="axisLine" x1="70" x2="850" y1="280" y2="280" />
          <line className="axisLine" x1="70" x2="70" y1="24" y2="280" />
          {prepared.zeroY !== null ? <line className="zeroLine" x1="70" x2="850" y1={prepared.zeroY} y2={prepared.zeroY} /> : null}
          {prepared.paths.filter((path) => path.area).map((path) => (
            <path className="chartArea" d={path.areaD} key={`${path.label}-area`} style={{ fill: `url(#${gradientId}-${slugify(path.label)})` }} />
          ))}
          {prepared.paths.map((path) => (
            <path className="chartLine" key={path.label} d={path.d} stroke={path.color} strokeDasharray={path.dashed ? "7 7" : undefined} />
          ))}
          {prepared.endpoints.map((point) => (
            <circle key={point.label} cx={point.x} cy={point.y} r="4" fill={point.color} />
          ))}
          {hover ? (
            <g>
              <line className="crosshairLine" x1={hoverPlotX} x2={hoverPlotX} y1="24" y2="280" />
              {prepared.seriesValues.map((values, seriesIndex) => {
                const value = values[hover.index];
                if (value == null) return null;
                return (
                  <circle
                    key={series[seriesIndex]?.label ?? seriesIndex}
                    cx={hoverPlotX}
                    cy={prepared.yFor(value)}
                    r="4.5"
                    fill="#ffffff"
                    stroke={series[seriesIndex]?.color}
                    strokeWidth="2.5"
                  />
                );
              })}
            </g>
          ) : null}
          <rect
            x="70"
            y="24"
            width="780"
            height="256"
            fill="transparent"
            onMouseMove={handleMove}
            onMouseLeave={() => setHover(null)}
          />
        </svg>
        {hover ? (
          <div
            className="chartTooltip"
            style={{ left: Math.min(Math.max(hover.x, 84), (containerRef.current?.clientWidth ?? 880) - 84), top: 8 }}
          >
            <strong>{hoverDate}</strong>
            {hoverRows.map((row) => (
              <span key={row.label}><i style={{ background: row.color }} />{row.label}: {row.value}</span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="chartStats">
        <span>Min: {valueFormat(prepared.min)}</span>
        <span>Max: {valueFormat(prepared.max)}</span>
        <span>Latest: {valueFormat(prepared.latestValue)}</span>
      </div>
    </section>
  );
}

function xForIndex(index: number, length: number) {
  return 70 + (index / Math.max(1, length - 1)) * 780;
}

function lastPoint(points: TimeSeriesPoint[]) {
  return points[points.length - 1];
}

function prepareSeries(series: ChartSeries[], includeZero: boolean) {
  const maxLength = Math.max(1, ...series.map((item) => item.points.length));
  const step = Math.max(1, Math.floor(maxLength / 140));
  const sampledSeries = series.map((item) => ({
    ...item,
    points: item.points.filter((_, index) => index % step === 0 || index === item.points.length - 1)
  }));
  const pointCount = Math.max(1, ...sampledSeries.map((item) => item.points.length));
  const allValues = sampledSeries.flatMap((item) => item.points.map((point) => point.value));
  const min = allValues.length ? Math.min(...allValues, ...(includeZero ? [0] : [])) : 0;
  const max = allValues.length ? Math.max(...allValues, ...(includeZero ? [0] : [])) : 1;
  const range = max - min || 1;
  const yTicks = Array.from({ length: 6 }, (_, index) => {
    const value = min + (range * index) / 5;
    const y = 280 - ((value - min) / range) * 256;
    return { value, y };
  }).reverse();
  const xFor = (index: number, length: number) => 70 + (index / Math.max(1, length - 1)) * 780;
  const yFor = (value: number) => 280 - ((value - min) / range) * 256;
  const paths = sampledSeries.map((item) => {
    const d = item.points.map((point, index) => `${index ? "L" : "M"} ${xFor(index, item.points.length).toFixed(1)} ${yFor(point.value).toFixed(1)}`).join(" ");
    const baselineY = Math.min(280, Math.max(24, yFor(0)));
    const firstX = xFor(0, item.points.length).toFixed(1);
    const lastX = xFor(item.points.length - 1, item.points.length).toFixed(1);
    return {
      label: item.label,
      color: item.color,
      dashed: item.dashed,
      area: item.area,
      d,
      areaD: item.area && item.points.length ? `${d} L ${lastX} ${baselineY.toFixed(1)} L ${firstX} ${baselineY.toFixed(1)} Z` : ""
    };
  });
  const endpoints = sampledSeries.map((item) => {
    const point = lastPoint(item.points) ?? { date: "", value: 0 };
    return {
      label: item.label,
      color: item.color,
      x: 850,
      y: yFor(point.value)
    };
  });
  const dateSource = sampledSeries.reduce((longest, item) => (item.points.length > longest.length ? item.points : longest), [] as TimeSeriesPoint[]);
  const dates = dateSource.map((point) => point.date);
  const tickCount = Math.min(6, pointCount);
  const xTicks = Array.from({ length: tickCount }, (_, index) => {
    const pointIndex = tickCount > 1 ? Math.round((index * (pointCount - 1)) / (tickCount - 1)) : 0;
    return { x: xFor(pointIndex, pointCount), date: dates[pointIndex] ?? "" };
  });
  const seriesValues = sampledSeries.map((item) => item.points.map((point) => point.value));
  return {
    paths,
    endpoints,
    yTicks,
    xTicks,
    dates,
    seriesValues,
    pointCount,
    yFor,
    zeroY: min <= 0 && max >= 0 ? yFor(0) : null,
    min,
    max,
    latestValue: lastPoint(series[0]?.points ?? [])?.value ?? 0,
    startDate: series[0]?.points[0]?.date ?? "",
    endDate: lastPoint(series[0]?.points ?? [])?.date ?? ""
  };
}
