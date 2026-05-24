import { Navigate } from "react-router-dom";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("vt_token");
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
