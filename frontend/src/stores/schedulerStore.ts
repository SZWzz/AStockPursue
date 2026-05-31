import { create } from "zustand";
import { api } from "@/lib/api";

interface ScheduledTask {
  id: string;
  name: string;
  task_type: string;
  cron_expression: string;
  config: Record<string, unknown>;
  enabled: boolean;
  next_run?: string;
  last_run?: string;
  last_status?: string;
}

interface TaskExecution {
  id: string;
  task_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  output_log: string;
  error_message: string;
}

interface SchedulerState {
  tasks: ScheduledTask[];
  loading: boolean;
  executions: TaskExecution[];
  executionsLoading: boolean;

  loadTasks: () => Promise<void>;
  createTask: (t: Partial<ScheduledTask>) => Promise<void>;
  updateTask: (id: string, u: Partial<ScheduledTask>) => Promise<void>;
  deleteTask: (id: string) => Promise<void>;
  toggleTask: (id: string, enabled: boolean) => Promise<void>;
  runNow: (id: string) => Promise<void>;
  loadExecutions: (taskId: string) => Promise<void>;
}

export const useSchedulerStore = create<SchedulerState>((set, get) => ({
  tasks: [],
  loading: false,
  executions: [],
  executionsLoading: false,

  loadTasks: async () => {
    set({ loading: true });
    try {
      const data = await (api as any).listSchedulerTasks();
      set({ tasks: data?.tasks || [], loading: false });
    } catch { set({ loading: false }); }
  },

  createTask: async (t) => {
    await (api as any).createSchedulerTask(t);
    await get().loadTasks();
  },

  updateTask: async (id, u) => {
    await (api as any).updateSchedulerTask(id, u);
    await get().loadTasks();
  },

  deleteTask: async (id) => {
    await (api as any).deleteSchedulerTask(id);
    await get().loadTasks();
  },

  toggleTask: async (id, enabled) => {
    if (enabled) await (api as any).resumeSchedulerTask(id);
    else await (api as any).pauseSchedulerTask(id);
    await get().loadTasks();
  },

  runNow: async (id) => {
    await (api as any).runSchedulerTaskNow(id);
    await get().loadExecutions(id);
  },

  loadExecutions: async (taskId) => {
    set({ executionsLoading: true });
    try {
      const data = await (api as any).getSchedulerTaskHistory(taskId);
      set({ executions: data?.executions || [], executionsLoading: false });
    } catch { set({ executionsLoading: false }); }
  },
}));
