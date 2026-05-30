import { Link } from "react-router-dom";
import { Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center px-4">
      <h1 className="text-6xl font-bold text-muted-foreground/30 mb-4">404</h1>
      <p className="text-lg text-muted-foreground mb-6">Page not found · 页面不存在</p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm hover:opacity-90 transition-opacity"
      >
        <Home className="w-4 h-4" />
        Back to Home · 返回首页
      </Link>
    </div>
  );
}
