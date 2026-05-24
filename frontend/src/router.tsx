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
const UserManagement = lazy(() =>
  import("@/pages/admin/UserManagement").then((m) => ({ default: m.UserManagement })),
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
      { path: "/alpha-zoo", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/bench", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/:alphaId", element: wrap(AlphaZoo) },
      { path: "/indicator-lab", element: wrap(IndicatorLab) },
      { path: "/strategy-lab", element: wrap(StrategyLab) },
      { path: "/paper-trading", element: wrap(PaperTrading) },
      { path: "/admin/users", element: wrap(UserManagement) },
    ],
  },
]);
