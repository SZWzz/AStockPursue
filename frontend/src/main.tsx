import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { Toaster } from "sonner";
import { I18nProvider } from "./lib/i18n";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { router } from "./router";
import { useAuthStore } from "./stores/auth";
import "highlight.js/styles/github-dark-dimmed.min.css";
import "./index.css";

// Restore JWT token from sessionStorage (tab-scoped)
useAuthStore.getState().loadFromStorage();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <I18nProvider>
        <RouterProvider router={router} />
        <Toaster position="bottom-right" richColors closeButton duration={3500} />
      </I18nProvider>
    </ErrorBoundary>
  </StrictMode>
);
