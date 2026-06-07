function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function hslToHex(hsl: string): string {
  if (!hsl) return "";
  const [h, s, l] = hsl.split(/\s+/).map(parseFloat);
  if (isNaN(h)) return "";
  const a = (s / 100) * Math.min(l / 100, 1 - l / 100);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l / 100 - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function isChinese(): boolean {
  if (localStorage.getItem("qa-lang") === "zh") return true;
  if (localStorage.getItem("qa-lang") === "en") return false;
  return (document.documentElement.lang || navigator.language || "").startsWith("zh");
}

let _cache: ReturnType<typeof buildTheme> | null = null;
let _cacheKey = "";

function buildTheme() {
  const cn = isChinese();

  // OLED dark chart colors — always dark, no light mode
  const gridHex = hslToHex(css("--chart-grid")) || "#1E293B";
  const textHex = hslToHex(css("--chart-text")) || "#94A3B8";
  const axisHex = hslToHex(css("--chart-axis")) || "#272F42";
  const successHex = hslToHex(css("--success")) || "#22C55E";
  const dangerHex = hslToHex(css("--danger")) || "#EF4444";
  const infoHex = hslToHex(css("--info")) || "#3B82F6";
  const warningHex = hslToHex(css("--warning")) || "#F59E0B";
  const primaryHex = hslToHex(css("--primary")) || "#FB923C";

  // Locale-aware candlestick colors
  const upHex = cn ? dangerHex : successHex;
  const downHex = cn ? successHex : dangerHex;

  return {
    // ECharts background
    backgroundColor: "#020617",

    // Grid & axes
    gridColor: gridHex,
    textColor: textHex,
    axisColor: axisHex,
    axisLabelColor: textHex,

    // Candlestick
    upColor: upHex,
    downColor: downHex,

    // MA lines
    maColors: [warningHex, "#8b5cf6", infoHex],

    // Bollinger band
    bollColor: "rgba(99,102,241,0.35)",

    // Volume bars
    volumeUp: upHex + "55",
    volumeDown: downHex + "55",

    // Crosshair & tooltip
    crosshairColor: "#334155",
    tooltipBg: "rgba(15,23,42,0.97)",
    tooltipBorder: "#334155",
    tooltipText: "#E2E8F0",
    tooltipSecondary: "#94A3B8",

    // Semantics
    infoColor: infoHex,
    warningColor: warningHex,
    primaryColor: primaryHex,
  };
}

export function getChartTheme() {
  const key = `${document.documentElement.lang || navigator.language}|${localStorage.getItem("qa-lang") || ""}`;
  if (_cache && _cacheKey === key) return _cache;
  _cache = buildTheme();
  _cacheKey = key;
  return _cache;
}
