import { useEffect, useState } from "react";
import { Trash2, Users, Shield } from "lucide-react";
import { authHeaders } from "@/lib/apiAuth";

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

  const loadUsers = async () => {
    try {
      const res = await fetch("/api/admin/users", { headers: authHeaders() });
      const data = await res.json();
      if (res.ok) setUsers(data.users || []);
      else setError(data.detail || "Failed to load users");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const deleteUser = async (id: number) => {
    if (!confirm("确定删除该用户？此操作不可撤销。")) return;
    await fetch(`/api/admin/users/${id}`, { method: "DELETE", headers: authHeaders() });
    loadUsers();
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Users className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">用户管理</h1>
      </div>

      {error && <div className="rounded-md bg-danger/10 px-4 py-3 text-sm text-danger">{error}</div>}

      {loading ? (
        <div className="text-sm text-muted-foreground">加载中...</div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium">用户名</th>
                <th className="text-left px-4 py-2.5 font-medium">邮箱</th>
                <th className="text-left px-4 py-2.5 font-medium">角色</th>
                <th className="text-left px-4 py-2.5 font-medium">LLM</th>
                <th className="text-left px-4 py-2.5 font-medium">Tushare</th>
                <th className="text-left px-4 py-2.5 font-medium">注册时间</th>
                <th className="text-right px-4 py-2.5 font-medium">操作</th>
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
                    {u.llm_provider ? `${u.llm_provider}/${u.llm_model}` : "未配置"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${u.tushare_configured ? "bg-success/10 text-success" : "bg-muted text-muted-foreground"}`}>
                      {u.tushare_configured ? "已配置" : "未配置"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs">{u.created_at?.slice(0, 10)}</td>
                  <td className="px-4 py-2.5 text-right">
                    {u.role !== "admin" && (
                      <button onClick={() => deleteUser(u.id)} className="p-1.5 text-muted-foreground hover:text-danger rounded transition">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
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
