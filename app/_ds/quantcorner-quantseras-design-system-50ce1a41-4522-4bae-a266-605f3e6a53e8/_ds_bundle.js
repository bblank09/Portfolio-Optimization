/* @ds-bundle: {"format":4,"namespace":"QuantCornerQuantSerasDesignSystem_50ce1a","components":[{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Surface","sourcePath":"components/core/Surface.jsx"},{"name":"DataTable","sourcePath":"components/data/DataTable.jsx"},{"name":"Metric","sourcePath":"components/data/Metric.jsx"},{"name":"Dialog","sourcePath":"components/feedback/Dialog.jsx"},{"name":"Status","sourcePath":"components/feedback/Status.jsx"},{"name":"Tooltip","sourcePath":"components/feedback/Tooltip.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Radio","sourcePath":"components/forms/Radio.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"}],"sourceHashes":{"components/core/Button.jsx":"f5021205d12c","components/core/Surface.jsx":"acb91e06ff10","components/data/DataTable.jsx":"16751f97fe71","components/data/Metric.jsx":"fdd77d92b0a8","components/feedback/Dialog.jsx":"26404ace74df","components/feedback/Status.jsx":"44c0d9846c61","components/feedback/Tooltip.jsx":"f635d6c3cf01","components/forms/Checkbox.jsx":"4af58ff0a7eb","components/forms/Input.jsx":"8e8e0be1935b","components/forms/Radio.jsx":"76f7945d97fd","components/forms/Select.jsx":"f44923d5c189","components/forms/Switch.jsx":"14428f8d9cb3","ui_kits/dashboard/Dashboard.jsx":"420b7261ddee","ui_kits/editorial/Editorial.jsx":"d6f49226a0f4"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.QuantCornerQuantSerasDesignSystem_50ce1a = window.QuantCornerQuantSerasDesignSystem_50ce1a || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-button", `
.qs-btn{font-family:var(--font-ui);font-weight:var(--weight-medium);border-radius:var(--radius-sm);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:var(--hit-target);padding:0 24px;font-size:15px;border:none;transition:background var(--motion-fast) var(--ease-standard),box-shadow var(--motion-fast) var(--ease-standard);}
.qs-btn:focus-visible{box-shadow:var(--focus-ring)}
.qs-btn[data-size="sm"]{min-height:36px;padding:0 16px;font-size:14px}
.qs-btn[data-variant="primary"]{background:var(--qs-primary);color:var(--qs-on-primary);box-shadow:var(--qs-shadow-2,0 1px 3px rgb(0 0 0 / 30%))}
.qs-btn[data-variant="primary"]:hover:not(:disabled){background:color-mix(in srgb, var(--qs-primary) 88%, white)}
.qs-btn[data-variant="primary"]:active:not(:disabled){background:var(--qs-primary-variant);color:#fff;box-shadow:none}
.qs-btn[data-variant="secondary"]{background:var(--qs-secondary);color:var(--qs-on-secondary)}
.qs-btn[data-variant="secondary"]:hover:not(:disabled){background:color-mix(in srgb, var(--qs-secondary) 85%, white)}
.qs-btn[data-variant="outlined"]{background:transparent;color:var(--qs-primary);border:1px solid var(--qs-border-strong)}
.qs-btn[data-variant="outlined"]:hover:not(:disabled){background:color-mix(in srgb, var(--qs-primary) 12%, transparent)}
.qs-btn[data-variant="text"]{background:transparent;color:var(--qs-primary);padding:0 12px}
.qs-btn[data-variant="text"]:hover:not(:disabled){background:color-mix(in srgb, var(--qs-primary) 12%, transparent)}
.qs-btn:disabled{color:var(--text-disabled);background:var(--qs-surface-4);border-color:transparent;cursor:not-allowed}
`);
function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  icon = null,
  style,
  children,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    className: "qs-btn",
    "data-variant": variant,
    "data-size": size,
    disabled: disabled,
    style: style
  }, rest), icon, children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Surface.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Surface({
  variant = "elevated",
  elevation = 1,
  padding = "24px",
  as: Tag = "div",
  style,
  children,
  ...rest
}) {
  const surfaceVar = variant === "elevated" ? `var(--qs-surface-${elevation})` : "var(--surface-canvas)";
  const base = {
    background: surfaceVar,
    borderRadius: "var(--radius-md)",
    padding,
    boxShadow: variant === "elevated" ? `var(--qs-shadow-${elevation > 8 ? 8 : elevation > 4 ? 4 : elevation > 1 ? 2 : 1}, none)` : "none",
    border: variant === "outlined" ? "1px solid var(--qs-border)" : "none"
  };
  return /*#__PURE__*/React.createElement(Tag, _extends({
    style: {
      ...base,
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Surface });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Surface.jsx", error: String((e && e.message) || e) }); }

// components/data/DataTable.jsx
try { (() => {
const {
  useState
} = React;
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-table", `
.qs-table{width:100%;border-collapse:collapse;font-size:14px}
.qs-table thead th{text-align:left;padding:10px 14px;color:var(--text-muted);font-weight:var(--weight-medium);font-size:12.5px;text-transform:uppercase;letter-spacing:.03em;border-bottom:1px solid var(--qs-border);cursor:pointer;user-select:none;white-space:nowrap}
.qs-table thead th[data-numeric="true"]{text-align:right}
.qs-table tbody td{padding:12px 14px;border-bottom:1px solid var(--qs-border);color:var(--text-body)}
.qs-table tbody td[data-numeric="true"]{text-align:right;font-family:var(--font-data);font-variant-numeric:tabular-nums}
.qs-table tbody tr:hover{background:var(--surface-card-hover)}
.qs-table-foot{padding:8px 14px;font-size:12px;color:var(--text-disabled);border-top:1px solid var(--qs-border)}
`);
function DataTable({
  columns,
  rows,
  source,
  cutoff
}) {
  const [sort, setSort] = useState(null);
  const sorted = sort ? [...rows].sort((a, b) => {
    const v = a[sort.key] > b[sort.key] ? 1 : a[sort.key] < b[sort.key] ? -1 : 0;
    return sort.dir === "asc" ? v : -v;
  }) : rows;
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("table", {
    className: "qs-table"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, columns.map(c => /*#__PURE__*/React.createElement("th", {
    key: c.key,
    "data-numeric": c.numeric ? "true" : "false",
    onClick: () => setSort(s => ({
      key: c.key,
      dir: s && s.key === c.key && s.dir === "asc" ? "desc" : "asc"
    }))
  }, c.label, sort && sort.key === c.key ? sort.dir === "asc" ? " ↑" : " ↓" : "")))), /*#__PURE__*/React.createElement("tbody", null, sorted.map((row, i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, columns.map(c => /*#__PURE__*/React.createElement("td", {
    key: c.key,
    "data-numeric": c.numeric ? "true" : "false"
  }, row[c.key])))))), (source || cutoff) && /*#__PURE__*/React.createElement("div", {
    className: "qs-table-foot"
  }, [source && `Source: ${source}`, cutoff && `Cutoff: ${cutoff}`].filter(Boolean).join("  ·  ")));
}
Object.assign(__ds_scope, { DataTable });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/DataTable.jsx", error: String((e && e.message) || e) }); }

// components/data/Metric.jsx
try { (() => {
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-metric", `
.qs-metric{display:flex;flex-direction:column;gap:4px}
.qs-metric-label{font-size:var(--text-label);color:var(--text-muted);font-weight:var(--weight-medium);text-transform:uppercase;letter-spacing:.04em}
.qs-metric-value-row{display:flex;align-items:baseline;gap:8px}
.qs-metric-value{font-family:var(--font-data);font-variant-numeric:tabular-nums;color:var(--text-body);font-weight:var(--weight-regular)}
.qs-metric[data-size="default"] .qs-metric-value{font-size:28px}
.qs-metric[data-size="hero"] .qs-metric-value{font-size:var(--text-hero);line-height:var(--text-hero-lh)}
.qs-metric-unit{font-size:14px;color:var(--text-muted)}
.qs-metric-compare{font-size:13px;font-weight:var(--weight-medium)}
.qs-metric-compare[data-dir="up"]{color:var(--qs-success)}
.qs-metric-compare[data-dir="down"]{color:var(--qs-error)}
.qs-metric-compare[data-dir="flat"]{color:var(--text-muted)}
.qs-metric-meta{font-size:12px;color:var(--text-disabled)}
`);
function Metric({
  label,
  value,
  unit,
  period,
  comparator,
  direction = "flat",
  size = "default",
  status
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "qs-metric",
    "data-size": size
  }, /*#__PURE__*/React.createElement("span", {
    className: "qs-metric-label"
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "qs-metric-value-row"
  }, /*#__PURE__*/React.createElement("span", {
    className: "qs-metric-value"
  }, value), unit && /*#__PURE__*/React.createElement("span", {
    className: "qs-metric-unit"
  }, unit), comparator && /*#__PURE__*/React.createElement("span", {
    className: "qs-metric-compare",
    "data-dir": direction
  }, comparator)), (period || status) && /*#__PURE__*/React.createElement("span", {
    className: "qs-metric-meta"
  }, [period, status].filter(Boolean).join(" · ")));
}
Object.assign(__ds_scope, { Metric });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Metric.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Dialog.jsx
try { (() => {
const {
  useEffect
} = React;
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-dialog", `
.qs-dialog-scrim{position:fixed;inset:0;background:rgb(0 0 0 / 55%);display:flex;align-items:center;justify-content:center;z-index:100}
.qs-dialog{background:var(--qs-surface-8);border-radius:var(--radius-md);box-shadow:var(--qs-shadow-8,0 16px 40px rgb(0 0 0 / 50%));min-width:360px;max-width:min(520px,90vw);padding:24px}
.qs-dialog h2{margin:0 0 8px;font-size:var(--text-title);font-weight:var(--weight-semibold);color:var(--text-body)}
.qs-dialog p{margin:0 0 20px;color:var(--text-muted);font-size:15px;line-height:1.5}
.qs-dialog-actions{display:flex;justify-content:flex-end;gap:12px}
`);
function Dialog({
  open,
  title,
  children,
  actions,
  onClose
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = e => e.key === "Escape" && onClose && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    className: "qs-dialog-scrim",
    onClick: onClose
  }, /*#__PURE__*/React.createElement("div", {
    className: "qs-dialog",
    role: "dialog",
    "aria-modal": "true",
    "aria-label": title,
    onClick: e => e.stopPropagation()
  }, /*#__PURE__*/React.createElement("h2", null, title), typeof children === "string" ? /*#__PURE__*/React.createElement("p", null, children) : children, /*#__PURE__*/React.createElement("div", {
    className: "qs-dialog-actions"
  }, actions)));
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Status.jsx
try { (() => {
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-status", `
.qs-status{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:var(--weight-medium);padding:4px 10px;border-radius:var(--radius-pill);line-height:1.3}
.qs-status[data-tone="neutral"]{background:var(--qs-surface-6);color:var(--text-muted)}
.qs-status[data-tone="info"]{background:color-mix(in srgb, var(--qs-info) 18%, transparent);color:var(--qs-info)}
.qs-status[data-tone="success"]{background:color-mix(in srgb, var(--qs-success) 18%, transparent);color:var(--qs-success)}
.qs-status[data-tone="warning"]{background:color-mix(in srgb, var(--qs-warning) 20%, transparent);color:var(--qs-warning)}
.qs-status[data-tone="error"]{background:color-mix(in srgb, var(--qs-error) 20%, transparent);color:var(--qs-error)}
.qs-status svg{width:14px;height:14px;flex:none}
`);
const GLYPHS = {
  neutral: "M8 1a7 7 0 100 14A7 7 0 008 1z",
  info: "M8 1a7 7 0 100 14A7 7 0 008 1zm0 4v5m0 2h.01",
  success: "M3 8l3.5 3.5L13 5",
  warning: "M8 1L1 14h14L8 1zm0 5v3m0 2h.01",
  error: "M8 1a7 7 0 100 14A7 7 0 008 1zm-2 5l4 4m0-4l-4 4"
};
function Status({
  tone = "neutral",
  children
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: "qs-status",
    "data-tone": tone
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: GLYPHS[tone]
  })), children);
}
Object.assign(__ds_scope, { Status });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Status.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Tooltip.jsx
try { (() => {
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-tooltip", `
.qs-tooltip-wrap{position:relative;display:inline-flex}
.qs-tooltip-bubble{position:absolute;bottom:calc(100% + 8px);left:50%;transform:translateX(-50%);background:var(--qs-surface-16);color:var(--text-body);font-size:12.5px;line-height:1.4;padding:6px 10px;border-radius:var(--radius-sm);box-shadow:var(--qs-shadow-4,0 4px 12px rgb(0 0 0 / 40%));white-space:nowrap;opacity:0;pointer-events:none;transition:opacity var(--motion-fast) var(--ease-standard);z-index:20}
.qs-tooltip-wrap:hover .qs-tooltip-bubble,.qs-tooltip-wrap:focus-within .qs-tooltip-bubble{opacity:1}
`);
function Tooltip({
  label,
  children
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: "qs-tooltip-wrap",
    tabIndex: 0
  }, children, /*#__PURE__*/React.createElement("span", {
    className: "qs-tooltip-bubble",
    role: "tooltip"
  }, label));
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Tooltip.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-check", `
.qs-check-row{display:flex;align-items:center;gap:10px;min-height:var(--hit-target);cursor:pointer;font-size:15px;color:var(--text-body)}
.qs-check-box{width:20px;height:20px;border-radius:4px;border:1.5px solid var(--qs-border-strong);display:inline-flex;align-items:center;justify-content:center;flex:none;transition:background var(--motion-fast) var(--ease-standard),border-color var(--motion-fast) var(--ease-standard)}
input:checked ~ .qs-check-box{background:var(--qs-primary);border-color:var(--qs-primary)}
.qs-check-row input{position:absolute;opacity:0;width:20px;height:20px;margin:0}
.qs-check-row input:focus-visible ~ .qs-check-box{box-shadow:var(--focus-ring)}
.qs-check-box svg{width:13px;height:13px;color:var(--qs-on-primary);opacity:0}
input:checked ~ .qs-check-box svg{opacity:1}
`);
function Checkbox({
  label,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", {
    className: "qs-check-row"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      display: "inline-flex"
    }
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "checkbox"
  }, rest)), /*#__PURE__*/React.createElement("span", {
    className: "qs-check-box"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M3 8l3.5 3.5L13 5"
  })))), label);
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-input", `
.qs-field{display:flex;flex-direction:column;gap:6px;font-family:var(--font-ui)}
.qs-field-label{font-size:13px;font-weight:var(--weight-medium);color:var(--text-body)}
.qs-input{background:var(--qs-surface-1);border:1px solid var(--qs-border-strong);border-radius:var(--radius-sm);color:var(--text-body);font-size:15px;padding:0 14px;min-height:var(--hit-target);font-family:inherit}
.qs-input:hover{border-color:var(--qs-text-medium)}
.qs-input:focus-visible{outline:none;border-color:var(--qs-primary);box-shadow:var(--focus-ring)}
.qs-input:disabled{color:var(--text-disabled);background:var(--qs-surface-4);cursor:not-allowed}
.qs-field-help{font-size:12.5px;color:var(--text-muted)}
.qs-field-help[data-error="true"]{color:var(--qs-error)}
`);
function Input({
  label,
  help,
  error,
  id,
  ...rest
}) {
  const fieldId = id || label?.toLowerCase().replace(/\s+/g, "-");
  return /*#__PURE__*/React.createElement("div", {
    className: "qs-field"
  }, label && /*#__PURE__*/React.createElement("label", {
    className: "qs-field-label",
    htmlFor: fieldId
  }, label), /*#__PURE__*/React.createElement("input", _extends({
    className: "qs-input",
    id: fieldId,
    "aria-invalid": !!error
  }, rest)), (help || error) && /*#__PURE__*/React.createElement("span", {
    className: "qs-field-help",
    "data-error": !!error
  }, error || help));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Radio.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-radio", `
.qs-radio-row{display:flex;align-items:center;gap:10px;min-height:var(--hit-target);cursor:pointer;font-size:15px;color:var(--text-body)}
.qs-radio-dot{width:20px;height:20px;border-radius:50%;border:1.5px solid var(--qs-border-strong);display:inline-flex;align-items:center;justify-content:center;flex:none}
.qs-radio-row input{position:absolute;opacity:0;width:20px;height:20px;margin:0}
input:checked ~ .qs-radio-dot{border-color:var(--qs-primary)}
input:checked ~ .qs-radio-dot::after{content:"";width:10px;height:10px;border-radius:50%;background:var(--qs-primary)}
.qs-radio-row input:focus-visible ~ .qs-radio-dot{box-shadow:var(--focus-ring)}
`);
function Radio({
  label,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", {
    className: "qs-radio-row"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      display: "inline-flex"
    }
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "radio"
  }, rest)), /*#__PURE__*/React.createElement("span", {
    className: "qs-radio-dot"
  })), label);
}
Object.assign(__ds_scope, { Radio });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Radio.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-select", `
.qs-select-wrap{position:relative}
.qs-select{appearance:none;background:var(--qs-surface-1);border:1px solid var(--qs-border-strong);border-radius:var(--radius-sm);color:var(--text-body);font-size:15px;padding:0 40px 0 14px;min-height:var(--hit-target);font-family:inherit;width:100%}
.qs-select:hover{border-color:var(--qs-text-medium)}
.qs-select:focus-visible{outline:none;border-color:var(--qs-primary);box-shadow:var(--focus-ring)}
.qs-select-chevron{position:absolute;right:14px;top:50%;transform:translateY(-50%);pointer-events:none;color:var(--text-muted)}
`);
function Select({
  label,
  options,
  id,
  ...rest
}) {
  const fieldId = id || label?.toLowerCase().replace(/\s+/g, "-");
  return /*#__PURE__*/React.createElement("div", {
    className: "qs-field"
  }, label && /*#__PURE__*/React.createElement("label", {
    className: "qs-field-label",
    htmlFor: fieldId
  }, label), /*#__PURE__*/React.createElement("div", {
    className: "qs-select-wrap"
  }, /*#__PURE__*/React.createElement("select", _extends({
    className: "qs-select",
    id: fieldId
  }, rest), options.map(o => /*#__PURE__*/React.createElement("option", {
    key: o.value,
    value: o.value
  }, o.label))), /*#__PURE__*/React.createElement("svg", {
    className: "qs-select-chevron",
    width: "16",
    height: "16",
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 6l4 4 4-4"
  }))));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function injectCss(id, css) {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const el = document.createElement("style");
  el.id = id;
  el.textContent = css;
  document.head.appendChild(el);
}
injectCss("qs-switch", `
.qs-switch-row{display:flex;align-items:center;gap:10px;min-height:var(--hit-target);cursor:pointer;font-size:15px;color:var(--text-body)}
.qs-switch-track{width:40px;height:24px;border-radius:var(--radius-pill);background:var(--qs-surface-6);position:relative;transition:background var(--motion-standard) var(--ease-standard);flex:none}
.qs-switch-row input{position:absolute;opacity:0;width:40px;height:24px;margin:0}
input:checked ~ .qs-switch-track{background:var(--qs-primary)}
.qs-switch-thumb{position:absolute;top:2px;left:2px;width:20px;height:20px;border-radius:50%;background:#fff;transition:transform var(--motion-standard) var(--ease-standard)}
input:checked ~ .qs-switch-track .qs-switch-thumb{transform:translateX(16px)}
.qs-switch-row input:focus-visible ~ .qs-switch-track{box-shadow:var(--focus-ring)}
`);
function Switch({
  label,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", {
    className: "qs-switch-row"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      display: "inline-flex"
    }
  }, /*#__PURE__*/React.createElement("input", _extends({
    type: "checkbox",
    role: "switch"
  }, rest)), /*#__PURE__*/React.createElement("span", {
    className: "qs-switch-track"
  }, /*#__PURE__*/React.createElement("span", {
    className: "qs-switch-thumb"
  }))), label);
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/Dashboard.jsx
try { (() => {
const {
  Surface,
  Button,
  Status,
  Metric,
  DataTable,
  Input,
  Select,
  Switch,
  Tooltip
} = window.QuantCornerQuantSerasDesignSystem_50ce1a;
const WATCHLIST_ROWS = [{
  ticker: "AAPL",
  price: "214.51",
  chg: "+1.2%",
  weight: "12.4%"
}, {
  ticker: "NVDA",
  price: "128.90",
  chg: "+3.4%",
  weight: "9.1%"
}, {
  ticker: "MSFT",
  price: "441.03",
  chg: "-0.4%",
  weight: "7.6%"
}, {
  ticker: "TSM",
  price: "186.22",
  chg: "+0.8%",
  weight: "5.2%"
}];
function TopBar({
  tab,
  setTab,
  theme,
  setTheme
}) {
  const tabs = ["Analysis", "Watchlist", "Screeners", "Factors", "API"];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 24,
      padding: "0 24px",
      height: 64,
      borderBottom: "1px solid var(--qs-border)",
      background: "var(--qs-surface-1)"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/brand/quantcorner-mark-dark.svg",
    style: {
      width: 26,
      height: 26
    },
    alt: ""
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 4
    }
  }, tabs.map(t => /*#__PURE__*/React.createElement("button", {
    key: t,
    onClick: () => setTab(t),
    style: {
      background: tab === t ? "var(--qs-surface-6)" : "transparent",
      color: tab === t ? "var(--text-body)" : "var(--text-muted)",
      border: "none",
      borderRadius: 6,
      padding: "8px 14px",
      fontSize: 14,
      fontWeight: 500,
      cursor: "pointer",
      fontFamily: "var(--font-ui)"
    }
  }, t))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      alignItems: "center",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Switch, {
    label: "Light theme",
    checked: theme === "light",
    onChange: e => setTheme(e.target.checked ? "light" : "dark")
  }), /*#__PURE__*/React.createElement(Status, {
    tone: "success"
  }, "API healthy")));
}
function AnalysisView() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 32,
      display: "flex",
      flexDirection: "column",
      gap: 24,
      maxWidth: 1040
    }
  }, /*#__PURE__*/React.createElement(Surface, {
    variant: "elevated",
    elevation: 2,
    style: {
      padding: 28
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: "var(--qs-secondary)",
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: ".04em",
      marginBottom: 8
    }
  }, "Interpretation"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-headline)",
      lineHeight: "var(--text-headline-lh)",
      fontWeight: 500,
      color: "var(--text-body)",
      marginBottom: 12
    }
  }, "AAPL risk-adjusted return has led its factor peers for 3 of the last 4 quarters."), /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--text-muted)",
      fontSize: 15,
      lineHeight: 1.6,
      marginBottom: 16
    }
  }, "Sharpe of 1.42 sits 0.18 above the internal factor benchmark over the trailing 12 months, driven mainly by lower realized volatility rather than higher raw return."), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: "var(--text-disabled)"
    }
  }, "Limitation: small sample (n=252 daily obs.); does not account for regime change. Illustrative data \u2014 not investment advice.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 24
    }
  }, /*#__PURE__*/React.createElement(Metric, {
    label: "Sharpe ratio",
    value: "1.42",
    size: "hero",
    period: "trailing 12mo",
    comparator: "+0.18 vs. benchmark",
    direction: "up",
    status: "illustrative"
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "Max drawdown",
    value: "-8.3%",
    period: "sample path, daily, not annualized",
    direction: "down",
    status: "illustrative"
  }), /*#__PURE__*/React.createElement(Metric, {
    label: "Volatility (ann.)",
    value: "14.6%",
    unit: "%",
    period: "trailing 12mo",
    status: "illustrative"
  })), /*#__PURE__*/React.createElement(Surface, {
    variant: "outlined",
    style: {
      padding: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "16px 20px",
      borderBottom: "1px solid var(--qs-border)",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: "var(--text-title)",
      fontWeight: 500,
      color: "var(--text-body)"
    }
  }, "Factor diagnostics"), /*#__PURE__*/React.createElement(Select, {
    label: "",
    options: [{
      value: "12m",
      label: "Trailing 12mo"
    }, {
      value: "3y",
      label: "Trailing 3yr"
    }],
    style: {
      minHeight: 36
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "0 20px 16px"
    }
  }, /*#__PURE__*/React.createElement(DataTable, {
    columns: [{
      key: "factor",
      label: "Factor"
    }, {
      key: "exposure",
      label: "Exposure",
      numeric: true
    }, {
      key: "contrib",
      label: "Contribution",
      numeric: true
    }],
    rows: [{
      factor: "Momentum",
      exposure: "0.62",
      contrib: "+2.1%"
    }, {
      factor: "Low volatility",
      exposure: "0.44",
      contrib: "+1.4%"
    }, {
      factor: "Quality",
      exposure: "0.31",
      contrib: "+0.6%"
    }, {
      factor: "Value",
      exposure: "-0.18",
      contrib: "-0.3%"
    }],
    source: "illustrative sample, internal factor model",
    cutoff: "2026-07-24"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12.5,
      color: "var(--text-disabled)",
      lineHeight: 1.6
    }
  }, "Method: rolling 12-month regression against a five-factor internal model. All figures are illustrative samples, not live data or a forecast."));
}
function WatchlistView() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 32,
      display: "flex",
      flexDirection: "column",
      gap: 20,
      maxWidth: 1040
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 12,
      alignItems: "flex-end"
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Add ticker",
    placeholder: "e.g. AMZN",
    style: {
      minWidth: 220
    }
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "primary"
  }, "Add to watchlist"), /*#__PURE__*/React.createElement(Button, {
    variant: "outlined"
  }, "Export CSV")), /*#__PURE__*/React.createElement(Surface, {
    variant: "outlined",
    style: {
      padding: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "16px 20px"
    }
  }, /*#__PURE__*/React.createElement(DataTable, {
    columns: [{
      key: "ticker",
      label: "Ticker"
    }, {
      key: "price",
      label: "Price",
      numeric: true
    }, {
      key: "chg",
      label: "Chg",
      numeric: true
    }, {
      key: "weight",
      label: "Weight",
      numeric: true
    }],
    rows: WATCHLIST_ROWS,
    source: "illustrative sample",
    cutoff: "2026-07-24"
  }))));
}
function Dashboard() {
  const [tab, setTab] = React.useState("Analysis");
  const [theme, setTheme] = React.useState("dark");
  React.useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: "100%",
      background: "var(--surface-canvas)"
    }
  }, /*#__PURE__*/React.createElement(TopBar, {
    tab: tab,
    setTab: setTab,
    theme: theme,
    setTheme: setTheme
  }), tab === "Analysis" && /*#__PURE__*/React.createElement(AnalysisView, null), tab === "Watchlist" && /*#__PURE__*/React.createElement(WatchlistView, null), (tab === "Screeners" || tab === "Factors" || tab === "API") && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 48,
      color: "var(--text-muted)",
      fontSize: 15
    }
  }, tab, " is not part of this recreation \u2014 the handoff package defines dashboard grammar and tokens, not this route's screen design."));
}
window.Dashboard = Dashboard;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/Dashboard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/editorial/Editorial.jsx
try { (() => {
const {
  Surface,
  Status,
  Button
} = window.QuantCornerQuantSerasDesignSystem_50ce1a;
const ROWS = [{
  n: "01",
  size: "lg",
  title: "Why factor crowding quietly erodes momentum strategies",
  dek: "A look at how correlated positioning across quant funds compresses the return this factor used to deliver.",
  tag: "Research",
  read: "9 min"
}, {
  n: "02",
  size: "md",
  title: "Reading the yield curve without overclaiming a recession call",
  dek: "The curve is a probability signal, not a countdown clock.",
  tag: "Macro",
  read: "6 min"
}, {
  n: "03",
  size: "md",
  title: "Backtests lie by omission — a checklist before you trust one",
  dek: "Survivorship, look-ahead bias, and the fee drag most backtests skip.",
  tag: "Method",
  read: "7 min"
}, {
  n: "04",
  size: "sm",
  title: "Three charts on realized vs. implied volatility this quarter",
  tag: "Chart",
  read: "3 min"
}, {
  n: "05",
  size: "sm",
  title: "What 'alpha decay' actually measures",
  tag: "Glossary",
  read: "2 min"
}];
function Row({
  r
}) {
  const titleSize = r.size === "lg" ? "var(--text-headline)" : r.size === "md" ? "var(--text-section)" : "var(--text-title)";
  const titleLh = r.size === "lg" ? "var(--text-headline-lh)" : "1.3";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 20,
      padding: "28px 0",
      borderBottom: "1px solid var(--qs-border)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-data)",
      fontSize: 15,
      color: "var(--text-disabled)",
      width: 32,
      flex: "none"
    }
  }, r.n), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10,
      alignItems: "center",
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement(Status, {
    tone: "neutral"
  }, r.tag), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12.5,
      color: "var(--text-disabled)"
    }
  }, r.read, " read")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: titleSize,
      lineHeight: titleLh,
      fontWeight: r.size === "lg" ? 500 : 500,
      color: "var(--text-body)",
      marginBottom: r.dek ? 8 : 0
    }
  }, r.title), r.dek && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 15,
      color: "var(--text-muted)",
      lineHeight: 1.6,
      maxWidth: 640
    }
  }, r.dek)));
}
function Editorial() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: "100%",
      background: "var(--surface-canvas)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 16,
      padding: "20px 32px",
      borderBottom: "1px solid var(--qs-border)"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/brand/quantcorner-wordmark-dark.svg",
    style: {
      height: 30,
      width: "auto"
    },
    alt: "QuantCorner"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      gap: 20,
      fontSize: 14,
      color: "var(--text-muted)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "Research"), /*#__PURE__*/React.createElement("span", null, "Macro"), /*#__PURE__*/React.createElement("span", null, "Community"))), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 760,
      margin: "0 auto",
      padding: "40px 32px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      color: "var(--qs-secondary)",
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: ".04em",
      marginBottom: 12
    }
  }, "This week's research"), ROWS.map(r => /*#__PURE__*/React.createElement(Row, {
    key: r.n,
    r: r
  }))));
}
window.Editorial = Editorial;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/editorial/Editorial.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Surface = __ds_scope.Surface;

__ds_ns.DataTable = __ds_scope.DataTable;

__ds_ns.Metric = __ds_scope.Metric;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.Status = __ds_scope.Status;

__ds_ns.Tooltip = __ds_scope.Tooltip;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Radio = __ds_scope.Radio;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Switch = __ds_scope.Switch;

})();
