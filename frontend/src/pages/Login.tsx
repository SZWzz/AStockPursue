import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, Loader2 } from "lucide-react";
import { useAuthStore } from "@/stores/auth";

export function Login() {
  const navigate = useNavigate();
  const { login, register } = useAuthStore();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    let err: string | null;
    if (isRegister) {
      err = await register(username, password, email || undefined);
      if (!err) err = await login(username, password);
    } else {
      err = await login(username, password);
    }
    setLoading(false);
    if (err) setError(err);
    else navigate("/");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 p-8">
        <div className="text-center space-y-2">
          <BarChart3 className="mx-auto h-10 w-10 text-primary" />
          <h1 className="text-xl font-bold">AStockPursue</h1>
          <p className="text-sm text-muted-foreground">
            {isRegister ? "创建新账号" : "登录您的账号"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">用户名</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="请输入用户名" required autoFocus />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">密码</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="请输入密码" required />
          </div>
          {isRegister && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium">邮箱（选填）</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="user@example.com" />
            </div>
          )}
          {error && (<div className="rounded-md bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>)}
          <button type="submit" disabled={loading} className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-70">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {isRegister ? "注册" : "登录"}
          </button>
        </form>

        <p className="text-center text-xs text-muted-foreground">
          {isRegister ? "已有账号？" : "没有账号？"}{" "}
          <button onClick={() => { setIsRegister(!isRegister); setError(null); }} className="font-medium text-primary hover:underline">
            {isRegister ? "去登录" : "注册"}
          </button>
        </p>
      </div>
    </div>
  );
}
