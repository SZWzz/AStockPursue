import { Suspense, lazy, type ComponentType } from "react";
import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import { AuthGuard } from "@/components/auth/AuthGuard";

const Agent = lazy(() => import("@/pages/Agent").then((m) => ({ default: m.Agent })));
const RunDetail = lazy(() =>
  import("@/pages/RunDetail").then((m) => ({ default: m.RunDetail })),
);
const Compare = lazy(() =>
  import("@/pages/Compare").then((m) => ({ default: m.Compare })),
);
const Settings = lazy(() =>
  import("@/pages/Settings").then((m) => ({ default: m.Settings })),
);
const Correlation = lazy(() =>
  import("@/pages/Correlation").then((m) => ({ default: m.Correlation })),
);
const Docs = lazy(() =>
  import("@/pages/Docs").then((m) => ({ default: m.Docs })),
);
const AlphaZoo = lazy(() =>
  import("@/pages/AlphaZoo").then((m) => ({ default: m.AlphaZoo })),
);
const IndicatorLab = lazy(() =>
  import("@/pages/IndicatorLab").then((m) => ({ default: m.IndicatorLab })),
);
const StrategyLab = lazy(() =>
  import("@/pages/StrategyLab").then((m) => ({ default: m.StrategyLab })),
);
const Login = lazy(() =>
  import("@/pages/Login").then((m) => ({ default: m.Login })),
);
const PaperTrading = lazy(() =>
  import("@/pages/PaperTrading").then((m) => ({ default: m.default })),
);
const Trading = lazy(() =>
  import("@/pages/Trading").then((m) => ({ default: m.Trading })),
);
const UserManagement = lazy(() =>
  import("@/pages/admin/UserManagement").then((m) => ({ default: m.UserManagement })),
);
const DataSourceStatus = lazy(() =>
  import("@/pages/DataSourceStatus").then((m) => ({ default: m.default })),
);
const FactorMining = lazy(() =>
  import("@/pages/FactorMining").then((m) => ({ default: m.FactorMining })),
);
const Screener = lazy(() =>
  import("@/pages/Screener").then((m) => ({ default: m.Screener })),
);
const Attribution = lazy(() =>
  import("@/pages/Attribution").then((m) => ({ default: m.Attribution })),
);
const Scheduler = lazy(() =>
  import("@/pages/Scheduler").then((m) => ({ default: m.Scheduler })),
);
const Marketplace = lazy(() =>
  import("@/pages/Marketplace").then((m) => ({ default: m.Marketplace })),
);
const Options = lazy(() =>
  import("@/pages/Options").then((m) => ({ default: m.Options })),
);
const Sentiment = lazy(() =>
  import("@/pages/Sentiment").then((m) => ({ default: m.Sentiment })),
);
const NotFound = lazy(() =>
  import("@/pages/NotFound").then((m) => ({ default: m.default })),
);

function PageLoader() {
  return (
    <div className="flex h-[60vh] items-center justify-center text-muted-foreground">
      Loading…
    </div>
  );
}

function wrap(Component: ComponentType) {
  return (
    <Suspense fallback={<PageLoader />}>
      <Component />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  { path: "/login", element: wrap(Login) },
  {
    element: <AuthGuard><Layout /></AuthGuard>,
    children: [
      { path: "/", element: wrap(Agent) },
      { path: "/settings", element: wrap(Settings) },
      { path: "/runs/:runId", element: wrap(RunDetail) },
      { path: "/compare", element: wrap(Compare) },
      { path: "/correlation", element: wrap(Correlation) },
      { path: "/docs", element: wrap(Docs) },
      { path: "/alpha-zoo", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/bench", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/:alphaId", element: wrap(AlphaZoo) },
      { path: "/indicator-lab", element: wrap(IndicatorLab) },
      { path: "/strategy-lab", element: wrap(StrategyLab) },
      { path: "/paper-trading", element: wrap(PaperTrading) },
      { path: "/trading", element: wrap(Trading) },
      { path: "/data-sources", element: wrap(DataSourceStatus) },
      { path: "/factor-mining", element: wrap(FactorMining) },
      { path: "/screener", element: wrap(Screener) },
      { path: "/attribution", element: wrap(Attribution) },
      { path: "/scheduler", element: wrap(Scheduler) },
      { path: "/marketplace", element: wrap(Marketplace) },
      { path: "/options", element: wrap(Options) },
      { path: "/sentiment", element: wrap(Sentiment) },
      { path: "/admin/users", element: wrap(UserManagement) },
      { path: "*", element: wrap(NotFound) },
    ],
  },
]);
