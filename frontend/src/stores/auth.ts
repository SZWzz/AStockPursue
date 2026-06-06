import { create } from "zustand";

interface UserInfo {
  user_id: number;
  username: string;
  role: string;
}

interface AuthState {
  token: string | null;
  user: UserInfo | null;
  loading: boolean;

  login: (username: string, password: string) => Promise<string | null>;
  register: (username: string, password: string, email?: string) => Promise<string | null>;
  logout: () => void;
  loadFromStorage: () => void;
}

// Security note: JWT is stored in sessionStorage (tab-scoped, cleared on close)
// rather than localStorage (persists across restarts, more XSS exposure).
// The backend also sets an httpOnly cookie for SSE endpoints.
const STORAGE = window.sessionStorage;

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  loading: false,

  login: async (username: string, password: string) => {
    set({ loading: true });
    try {
      const res = await fetch("/v1/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        set({ loading: false });
        return body.detail || "Login failed";
      }
      const data = await res.json();
      const token = data.token as string;
      const user: UserInfo = { user_id: data.user_id, username: data.username, role: data.role };
      // Use sessionStorage instead of localStorage — cleared when tab closes
      STORAGE.setItem("vt_token", token);
      STORAGE.setItem("vt_user", JSON.stringify(user));
      set({ token, user, loading: false });
      return null;
    } catch (e) {
      set({ loading: false });
      return String(e);
    }
  },

  register: async (username: string, password: string, email?: string) => {
    set({ loading: true });
    try {
      const res = await fetch("/v1/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, email }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        set({ loading: false });
        return body.detail || "Registration failed";
      }
      set({ loading: false });
      return null;
    } catch (e) {
      set({ loading: false });
      return String(e);
    }
  },

  logout: () => {
    STORAGE.removeItem("vt_token");
    STORAGE.removeItem("vt_user");
    set({ token: null, user: null });
  },

  loadFromStorage: () => {
    const token = STORAGE.getItem("vt_token");
    const userStr = STORAGE.getItem("vt_user");
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr) as UserInfo;
        set({ token, user });
      } catch {
        STORAGE.removeItem("vt_token");
        STORAGE.removeItem("vt_user");
        set({ token: null, user: null });
      }
    }
  },
}));
