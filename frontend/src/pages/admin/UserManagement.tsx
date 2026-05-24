import { useEffect, useState } from "react";
import { Trash2, Users, Shield, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
  llm_provider: string;
  llm_model: string;
  tushare_configured: boolean;
}

export function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { t } = useI18n();

  const loadUsers = async () => {
    try {
      const data = await api.listUsers();
      setUsers(data.users || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : t.failedToLoadUsers);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteUser(deleteTarget.id);
      setDeleteTarget(null);
      loadUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.failedToLoadUsers);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Users className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">{t.userManagement}</h1>
      </div>

      {error && <div className="rounded-md bg-danger/10 px-4 py-3 text-sm text-danger">{error}</div>}

      {loading ? (
        <div className="text-sm text-muted-foreground">{t.loading}</div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium">{t.username_col}</th>
                <th className="text-left px-4 py-2.5 font-medium">{t.email_col}</th>
                <th className="text-left px-4 py-2.5 font-medium">{t.role_col}</th>
                <th className="text-left px-4 py-2.5 font-medium">{t.llm_col}</th>
                <th className="text-left px-4 py-2.5 font-medium">{t.tushare_col}</th>
                <th className="text-left px-4 py-2.5 font-medium">{t.registered_col}</th>
                <th className="text-right px-4 py-2.5 font-medium">{t.actions_col}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t hover:bg-muted/30 transition">
                  <td className="px-4 py-2.5 font-medium">{u.username}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{u.email || "—"}</td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${u.role === "admin" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
                      {u.role === "admin" && <Shield className="h-3 w-3" />}
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs">
                    {u.llm_provider ? `${u.llm_provider}/${u.llm_model}` : t.notConfigured}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${u.tushare_configured ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"}`}>
                      {u.tushare_configured ? t.configured : t.notConfigured}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs">{u.created_at?.slice(0, 10)}</td>
                  <td className="px-4 py-2.5 text-right">
                    {u.role !== "admin" && (
                      deleteTarget?.id === u.id ? (
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className="text-danger flex items-center gap-1"><AlertTriangle className="h-3 w-3" />{t.confirmDeleteUser}</span>
                          <button onClick={handleDeleteConfirm} disabled={deleting} className="px-2 py-0.5 rounded bg-danger text-danger-foreground hover:opacity-90 disabled:opacity-50 transition">
                            {deleting ? t.deletingUser : t.confirmDelete}
                          </button>
                          <button onClick={() => setDeleteTarget(null)} disabled={deleting} className="px-2 py-0.5 rounded border text-muted-foreground hover:bg-muted transition">
                            {t.cancelDelete}
                          </button>
                        </span>
                      ) : (
                        <button onClick={() => setDeleteTarget(u)} className="p-1.5 text-muted-foreground hover:text-danger rounded transition">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
