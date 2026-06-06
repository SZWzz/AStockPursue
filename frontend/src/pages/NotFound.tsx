import { Link } from "react-router-dom";
import { Home } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center px-4">
      <h1 className="text-6xl font-bold text-muted-foreground/30 mb-4">404</h1>
      <p className="text-lg text-muted-foreground mb-6">{(t as any).notFound}</p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm hover:opacity-90 transition-opacity"
      >
        <Home className="w-4 h-4" />
        {(t as any).notFoundBack}
      </Link>
    </div>
  );
}
