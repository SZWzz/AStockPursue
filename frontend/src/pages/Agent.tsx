import { useEffect, useRef, useState, useMemo, useCallback, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Send, Loader2, ArrowDown, Square, Download, Plus, Paperclip, X, Users, BarChart3 } from "lucide-react";
import { toast } from "sonner";
import { useAgentStore } from "@/stores/agent";
import { useSSE } from "@/hooks/useSSE";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";
import type { AgentMessage, ToolCallEntry } from "@/types/agent";
import { AgentAvatar } from "@/components/chat/AgentAvatar";
import { RightSidebar } from "@/components/chat/RightSidebar";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ThinkingTimeline } from "@/components/chat/ThinkingTimeline";
import { ConversationTimeline } from "@/components/chat/ConversationTimeline";
import { ToolProgressIndicator } from "@/components/chat/ToolProgressIndicator";

/* ---------- Message grouping ---------- */
type MsgGroup =
  | { kind: "single"; msg: AgentMessage }
  | { kind: "timeline"; msgs: AgentMessage[] };

function groupMessages(msgs: AgentMessage[]): MsgGroup[] {
  const out: MsgGroup[] = [];
  let buf: AgentMessage[] = [];
  const flush = () => { if (buf.length) { out.push({ kind: "timeline", msgs: [...buf] }); buf = []; } };
  for (const m of msgs) {
    if (["thinking", "tool_call", "tool_result", "compact"].includes(m.type)) {
      buf.push(m);
    } else {
      flush();
      out.push({ kind: "single", msg: m });
    }
  }
  flush();
  return out;
}

const act = () => useAgentStore.getState();

/* ---------- Component ---------- */
export function Agent() {
  const [input, setInput] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sseSessionRef = useRef<string | null>(null);
  const prevSseStatusRef = useRef<string>("disconnected");
  const genRef = useRef(0);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(() => localStorage.getItem("qa-right-sidebar") === "collapsed");
  const toggleRightPanel = () => {
    const next = !rightPanelCollapsed;
    setRightPanelCollapsed(next);
    localStorage.setItem("qa-right-sidebar", next ? "collapsed" : "expanded");
  };
  const lastEventRef = useRef(0);

  /* tool_progress coalescing — keep latest payload per-tool, flush once per rAF. */
  const pendingProgressRef = useRef<Map<string, NonNullable<ToolCallEntry["progress"]>>>(new Map());
  const progressRafRef = useRef(0);

  const [attachment, setAttachment] = useState<{ filename: string; filePath: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const uploadMenuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [swarmPreset, setSwarmPreset] = useState<{ name: string; title: string } | null>(null);

  const messages = useAgentStore(s => s.messages);
  const streamingText = useAgentStore(s => s.streamingText);
  const status = useAgentStore(s => s.status);
  const sessionId = useAgentStore(s => s.sessionId);
  const toolCalls = useAgentStore(s => s.toolCalls);
  const sessionLoading = useAgentStore(s => s.sessionLoading);

  const { connect, disconnect, onStatusChange } = useSSE();
  const { t } = useI18n();

  const urlSessionId = searchParams.get("session");

  /* Smart scroll — only auto-scroll when near bottom */
  const isNearBottom = useCallback(() => {
    const el = listRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 100;
  }, []);

  const rafRef = useRef(0);
  const scrollToBottom = useCallback(() => {
    if (!isNearBottom()) {
      setShowScrollBtn(true);
      return;
    }
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
    });
  }, [isNearBottom]);

  const forceScrollToBottom = useCallback(() => {
    setShowScrollBtn(false);
    requestAnimationFrame(() => {
      if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
    });
  }, []);

  // Check for pending prompt from other pages (e.g. Correlation AI analysis)
  useEffect(() => {
    const pending = localStorage.getItem("vr_pending_prompt");
    if (pending) {
      localStorage.removeItem("vr_pending_prompt");
      setInput(pending);
      inputRef.current?.focus();
    }
  }, []);

  /* Track scroll position to show/hide scroll button */
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const onScroll = () => {
      if (isNearBottom()) setShowScrollBtn(false);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [isNearBottom]);

  useEffect(() => {
    onStatusChange((s) => {
      act().setSseStatus(s);
      if (s === "reconnecting" && prevSseStatusRef.current === "connected") toast.warning(t.reconnecting);
      else if (s === "connected" && prevSseStatusRef.current === "reconnecting") toast.success(t.connected);
      else if (s === "disconnected" && prevSseStatusRef.current === "reconnecting") {
        // Gave up after max retries — session likely deleted or server unreachable
        toast.error(t.sessionGone || "会话已失效，请新建对话");
      }
      prevSseStatusRef.current = s;
    });
  }, [onStatusChange, t]);

  const doDisconnect = useCallback(() => {
    disconnect();
    sseSessionRef.current = null;
  }, [disconnect]);

  const loadSessionMessages = useCallback(async (sid: string, gen: number) => {
    try {
      const msgs = await api.getSessionMessages(sid);
      if (genRef.current !== gen) return;
      const agentMsgs: AgentMessage[] = [];
      for (const m of msgs) {
        const meta = m.metadata as Record<string, unknown> | undefined;
        const runId = meta?.run_id as string | undefined;
        const metrics = meta?.metrics as Record<string, number> | undefined;
        const ts = new Date(m.created_at).getTime();
        if (m.role === "user") {
          agentMsgs.push({ id: m.message_id, type: "user", content: m.content, timestamp: ts });
        } else if (runId) {
          if (m.content && m.content !== t.agentStrategyCompleted) {
            agentMsgs.push({ id: m.message_id + "_ans", type: "answer", content: m.content, timestamp: ts });
          }
          agentMsgs.push({ id: m.message_id, type: "run_complete", content: "", runId, metrics, timestamp: ts + 1 });
        } else {
          agentMsgs.push({ id: m.message_id, type: "answer", content: m.content, timestamp: ts });
        }
      }
      if (genRef.current !== gen) return;
      act().loadHistory(agentMsgs);
      act().cacheSession(sid, agentMsgs);
      setTimeout(() => forceScrollToBottom(), 50);
    } finally {
      // Always reset loading, even on early gen-check returns
      if (genRef.current === gen) {
        act().setSessionLoading(false);
      }
    }
  }, [forceScrollToBottom]);

  const setupSSE = useCallback((sid: string) => {
    if (sseSessionRef.current === sid) return;
    disconnect();
    sseSessionRef.current = sid;

    const touch = () => { lastEventRef.current = Date.now(); };

    connect(api.sseUrl(sid), {
      text_delta: (d) => { touch(); act().appendDelta(String(d.delta || "")); scrollToBottom(); },
      thinking_done: () => { touch(); /* don't flush — keep streaming text visible */ },

      tool_call: (d) => {
        touch();
        const toolName = String(d.tool || "");
        // Only update toolCalls tracker (no message creation during streaming)
        act().addToolCall({
          id: toolName, tool: toolName,
          arguments: (d.arguments as Record<string, string>) ?? {},
          status: "running", timestamp: Date.now(),
        });
        scrollToBottom();
      },

      tool_result: (d) => {
        touch();
        const toolName = String(d.tool || "");
        // Drop any in-flight coalesced progress for this tool.
        pendingProgressRef.current.delete(toolName);
        // Only update tracker (no message creation during streaming)
        act().updateToolCall(toolName, {
          status: d.status === "ok" ? "ok" : "error",
          preview: String(d.preview || ""),
          elapsed_ms: Number(d.elapsed_ms || 0),
          elapsed_s: undefined,
          progress: undefined,
        });
      },

      tool_heartbeat: (d) => {
        touch();
        const toolName = String(d.tool || "");
        if (!toolName) return;
        act().updateToolCall(toolName, {
          elapsed_s: Number(d.elapsed_s || 0),
        });
      },

      tool_progress: (d) => {
        touch();
        const toolName = String(d.tool || "");
        if (!toolName) return;
        const payload: NonNullable<ToolCallEntry["progress"]> = {};
        if (typeof d.stage === "string" && d.stage) payload.stage = d.stage;
        if (typeof d.message === "string" && d.message) payload.message = d.message;
        if (typeof d.current === "number") payload.current = d.current;
        if (typeof d.total === "number") payload.total = d.total;
        // Coalesce: keep latest payload per tool, flush once per animation frame.
        pendingProgressRef.current.set(toolName, payload);
        if (progressRafRef.current) return;
        progressRafRef.current = requestAnimationFrame(() => {
          progressRafRef.current = 0;
          const pending = pendingProgressRef.current;
          if (pending.size === 0) return;
          const store = act();
          for (const [tool, progress] of pending) {
            store.updateToolCall(tool, { progress });
          }
          pending.clear();
        });
      },

      compact: () => { touch(); },

      "attempt.completed": async (d) => {
        touch();
        const s = act();
        // Build ThinkingTimeline summary from accumulated toolCalls
        const completedTools = s.toolCalls;
        if (completedTools.length > 0) {
          for (const tc of completedTools) {
            s.addMessage({ id: tc.id + "_call", type: "tool_call", content: "", tool: tc.tool, args: tc.arguments, status: tc.status || "ok", timestamp: tc.timestamp });
            if (tc.elapsed_ms != null) {
              s.addMessage({ id: "", type: "tool_result", content: tc.preview || "", tool: tc.tool, status: tc.status || "ok", elapsed_ms: tc.elapsed_ms, timestamp: tc.timestamp + 1 });
            }
          }
        }

        // Clear streaming text (don't create thinking message)
        s.clearStreaming();

        // Add final answer
        const runDir = String(d.run_dir || "");
        const runId = runDir ? runDir.split(/[/\\]/).pop() : undefined;
        const summary = String(d.summary || "");
        if (summary) s.addMessage({ id: "", type: "answer", content: summary, timestamp: Date.now() });

        // Detect Shadow Account id if render_shadow_report fired successfully this turn
        const shadowCall = completedTools.find(
          (tc) => tc.tool === "render_shadow_report" && (tc.status || "ok") === "ok",
        );
        const shadowMatch = shadowCall?.preview?.match(/"shadow_id"\s*:\s*"(shadow_[A-Za-z0-9_]+)"/);
        const shadowId = shadowMatch?.[1];

        // Show RunCompleteCard whenever a run completed (with or without metrics)
        if (runId) {
          try {
            const runData = await api.getRun(runId);
            s.addMessage({
              id: "", type: "run_complete", content: "", runId,
              metrics: runData.metrics && Object.keys(runData.metrics).length > 0 ? runData.metrics : undefined,
              equityCurve: runData.equity_curve?.map(e => ({ time: e.time, equity: e.equity })),
              shadowId,
              timestamp: Date.now(),
            });
          } catch {
            // Show card even if getRun fails — user can still click through
            s.addMessage({ id: "", type: "run_complete", content: "", runId, shadowId, timestamp: Date.now() });
          }
        } else if (shadowId) {
          s.addMessage({ id: "", type: "run_complete", content: "", shadowId, timestamp: Date.now() });
        }

        // Reset
        s.setStatus("idle");
        useAgentStore.setState({ toolCalls: [] });
        scrollToBottom();
      },

      "attempt.failed": (d) => {
        touch();
        act().clearStreaming();
        act().addMessage({ id: "", type: "error", content: String(d.error || t.agentExecutionFailed), timestamp: Date.now() });
        act().setStatus("idle");
        // Clear stale toolCalls so the next turn's running indicator doesn't
        // briefly show the previous turn's progress before fresh events land.
        useAgentStore.setState({ toolCalls: [] });
        scrollToBottom();
      },

      heartbeat: () => {},
      reconnect: (d) => { act().setSseStatus("reconnecting", Number(d.attempt ?? 0)); },
    });
  }, [connect, disconnect, scrollToBottom]);

  useEffect(() => {
    const gen = ++genRef.current;
    const { sessionId: curSid, messages: curMsgs, status, cacheSession, reset, getCachedSession, switchSession } = act();

    if (urlSessionId && urlSessionId !== curSid) {
      doDisconnect();
      if (curSid && curMsgs.length > 0) cacheSession(curSid, curMsgs);

      const cached = getCachedSession(urlSessionId);
      switchSession(urlSessionId, cached);
      if (cached) {
        setTimeout(() => forceScrollToBottom(), 50);
      } else {
        loadSessionMessages(urlSessionId, gen);
      }
      setupSSE(urlSessionId);
    } else if (urlSessionId && urlSessionId === curSid && status === "streaming") {
      // Navigated back — re-establish SSE if agent is still running
      setupSSE(urlSessionId);
    } else if (!urlSessionId && curSid) {
      doDisconnect();
      if (curMsgs.length > 0) cacheSession(curSid, curMsgs);
      reset();
    }
  }, [urlSessionId, doDisconnect, loadSessionMessages, setupSSE, forceScrollToBottom]);

  // Don't disconnect SSE on unmount — let the agent keep running in background
  // The connection will be cleaned up when the session completes or user switches session

  /* Safety timeout: if streaming but no SSE event for 90s, reset to idle */
  useEffect(() => {
    if (status !== "streaming") return;
    const timer = setInterval(() => {
      if (lastEventRef.current && Date.now() - lastEventRef.current > 90_000 && act().status === "streaming") {
        act().setStatus("idle");
        toast.warning(t.executionTimeout);
      }
    }, 10_000);
    return () => clearInterval(timer);
  }, [status]);

  const runPrompt = async (prompt: string) => {
    if (!prompt.trim() || status === "streaming") return;

    let finalPrompt = prompt;

    // Swarm mode: let agent auto-select the right preset
    if (swarmPreset) {
      setSwarmPreset(null);
      finalPrompt = `[Swarm Team Mode] Use the swarm tool to assemble the best specialist team for this task. Auto-select the most appropriate preset.\n\n${prompt}`;
    }

    if (attachment) {
      finalPrompt = `[Uploaded file: ${attachment.filename}, path: ${attachment.filePath}]\n\n${finalPrompt}`;
      setAttachment(null);
    }
    setInput("");
    act().addMessage({ id: "", type: "user", content: finalPrompt, timestamp: Date.now() });
    act().setStatus("streaming");
    forceScrollToBottom();
    inputRef.current?.focus();

    try {
      let sid = act().sessionId;
      if (!sid) {
        const session = await api.createSession(prompt.slice(0, 50));
        sid = session.session_id;
        act().setSessionId(sid);
        setSearchParams({ session: sid }, { replace: true });
      }
      setupSSE(sid);
      await api.sendMessage(sid, finalPrompt);
    } catch {
      act().setStatus("error");
      toast.error(t.sendFailed);
      act().addMessage({ id: "", type: "error", content: t.sendFailed, timestamp: Date.now() });
    }
  };

  const handleSubmit = (e: FormEvent) => { e.preventDefault(); runPrompt(input.trim()); };

  const handleCancel = async () => {
    if (!sessionId) {
      act().setStatus("idle");
      return;
    }
    try {
      await api.cancelSession(sessionId);
      act().setStatus("idle");
      act().clearStreaming();
      useAgentStore.setState({ toolCalls: [] });
      toast.info(t.cancelSent);
    } catch {
      toast.error(t.cancelFailed);
    }
  };

  const handleRetry = useCallback((errorMsg: AgentMessage) => {
    if (status === "streaming") return;
    const msgs = act().messages;
    const errorIdx = msgs.findIndex(m => m.id === errorMsg.id);
    if (errorIdx === -1) return;
    // Find the most recent user message before this error
    let userContent: string | null = null;
    for (let i = errorIdx - 1; i >= 0; i--) {
      if (msgs[i].type === "user") {
        userContent = msgs[i].content;
        break;
      }
    }
    if (!userContent) return;
    runPrompt(userContent);
  }, [status]);

  const handleExport = () => {
    if (messages.length === 0) return;
    const lines: string[] = [t.exportTitle, ``, `${t.exportTime}: ${new Date().toLocaleString()}`, ``];
    for (const msg of messages) {
      const time = new Date(msg.timestamp).toLocaleString();
      if (msg.type === "user") {
        lines.push(`${t.exportUser} (${time})`, ``, msg.content, ``);
      } else if (msg.type === "answer") {
        lines.push(`${t.exportAssistant} (${time})`, ``, msg.content, ``);
      } else if (msg.type === "error") {
        lines.push(`${t.exportError} (${time})`, ``, msg.content, ``);
      } else if (msg.type === "tool_call") {
        lines.push(`${t.exportToolCall}: ${msg.tool || "unknown"}`, ``);
      } else if (msg.type === "run_complete") {
        lines.push(`${t.exportRunComplete}: ${msg.runId || ""}`, ``);
      }
    }
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    const blockedExts = [
      ".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".app", ".dmg",
      ".so", ".dll", ".dylib",
      ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz",
    ];
    const lowered = file.name.toLowerCase();
    if (blockedExts.some((ext) => lowered.endsWith(ext))) {
      toast.error(t.executablesBlocked);
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      toast.error(t.fileSizeExceeded);
      return;
    }
    setUploading(true);
    setShowUploadMenu(false);
    try {
      const result = await api.uploadFile(file);
      setAttachment({ filename: result.filename, filePath: result.file_path });
      toast.success(t.uploadedFile.replace("{name}", result.filename));
    } catch (err) {
      toast.error(t.uploadFailed.replace("{reason}", err instanceof Error ? err.message : t.agentUnknownError));
    } finally {
      setUploading(false);
    }
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (uploadMenuRef.current && !uploadMenuRef.current.contains(e.target as Node)) {
        setShowUploadMenu(false);
      }
    };
    if (showUploadMenu) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showUploadMenu]);

  const groups = useMemo(() => groupMessages(messages), [messages]);

  return (
    <div className="flex h-[calc(100vh-3rem)]">
      {/* Left: Chat area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
      <div ref={listRef} className="flex-1 overflow-auto scroll-smooth relative">
        <div className="max-w-3xl mx-auto space-y-5 px-6 pt-8">
          {sessionLoading && (
            <div className="space-y-5 py-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="flex gap-3 animate-pulse">
                  <div className="h-9 w-9 rounded-xl bg-muted shrink-0" />
                  <div className="flex-1 space-y-2.5">
                    <div className="h-4 bg-muted rounded-lg w-3/4" />
                    <div className="h-3 bg-muted/50 rounded-lg w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          )}
          {!sessionLoading && messages.length === 0 && (
            <div className="flex items-center justify-center min-h-[50vh]">
              <div className="text-center space-y-4 animate-fade-in">
                <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto">
                  <BarChart3 className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <div className="text-xl font-bold tracking-tight">AStockPursue</div>
                  <p className="text-sm text-muted-foreground mt-1.5">{t.agentSubtitle}</p>
                </div>
                <p className="text-sm text-muted-foreground/70 max-w-md mx-auto">
                  {t.agentWelcomeHint}
                </p>
              </div>
            </div>
          )}

          {groups.map((g, i) => {
            if (g.kind === "timeline") {
              return (
                <ThinkingTimeline
                  key={g.msgs[0].id || g.msgs[0].timestamp}
                  messages={g.msgs}
                  isLatest={i === groups.length - 1 && status === "streaming"}
                />
              );
            }
            const msgIdx = messages.indexOf(g.msg);
            return (
              <div key={g.msg.id || g.msg.timestamp} data-msg-idx={msgIdx}>
                <MessageBubble msg={g.msg} onRetry={g.msg.type === "error" ? handleRetry : undefined} />
              </div>
            );
          })}

          {/* Pre-stream placeholder: visible after Send, before first SSE event */}
          {status === "streaming" && !streamingText && toolCalls.length === 0 && (
            <div className="flex gap-3 animate-fade-in">
              <AgentAvatar />
              <div className="flex-1 min-w-0 flex items-center gap-2 text-sm text-muted-foreground pt-0.5">
                <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
                <span>{t.thinking}</span>
              </div>
            </div>
          )}

          {/* Live streaming area: text + tool status */}
          {(streamingText || (status === "streaming" && toolCalls.length > 0)) && (
            <div className="flex gap-3">
              <AgentAvatar />
              <div className="flex-1 min-w-0 space-y-2">
                {streamingText && (
                  <div className="prose prose-sm dark:prose-invert max-w-none leading-relaxed text-sm">
                    {streamingText}
                    <span className="inline-block w-0.5 h-4 bg-primary ml-0.5 animate-pulse align-middle" />
                  </div>
                )}
                {status === "streaming" && toolCalls.length > 0 && (
                  <ToolProgressIndicator toolCalls={toolCalls} />
                )}
              </div>
            </div>
          )}

        </div>

        {/* Scroll to bottom button */}
        {showScrollBtn && (
          <button
            onClick={forceScrollToBottom}
            className="sticky bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-4 py-2 rounded-full bg-primary text-primary-foreground text-sm font-medium shadow-lg hover:brightness-110 transition-all duration-150 z-10 animate-fade-in"
          >
            <ArrowDown className="h-4 w-4" /> {t.newMessages}
          </button>
        )}
        <ConversationTimeline messages={messages} containerRef={listRef} />
      </div>

      <form onSubmit={handleSubmit} className="border-t px-4 pt-4 pb-6 bg-background/80 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto space-y-2.5">
          {/* Swarm preset badge */}
          {swarmPreset && (
            <div className="flex items-center gap-1 animate-fade-in">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-400 text-sm font-medium">
                <Users className="h-3.5 w-3.5" />
                {swarmPreset.title}
                <button type="button" onClick={() => setSwarmPreset(null)} className="hover:text-destructive transition-colors ml-0.5">
                  <X className="h-3.5 w-3.5" />
                </button>
              </span>
            </div>
          )}
          {/* Attachment badge */}
          {attachment && (
            <div className="flex items-center gap-1 animate-fade-in">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-sm font-medium">
                <Paperclip className="h-3.5 w-3.5" />
                {attachment.filename}
                <button type="button" onClick={() => setAttachment(null)} className="hover:text-destructive transition-colors ml-0.5">
                  <X className="h-3.5 w-3.5" />
                </button>
              </span>
            </div>
          )}
          {/* Uploading indicator */}
          {uploading && (
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {t.uploading}
            </div>
          )}
          <div className="flex gap-2 items-end">
            {/* "+" menu: PDF upload + Swarm presets */}
            <div className="relative" ref={uploadMenuRef}>
              <button
                type="button"
                onClick={() => setShowUploadMenu(prev => !prev)}
                disabled={status === "streaming" || uploading}
                className="w-10 h-10 rounded-xl border bg-card flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-muted/50 transition-all duration-150 disabled:opacity-40 shrink-0 shadow-sm"
                title={t.moreOptions}
              >
                <Plus className="h-4.5 w-4.5" />
              </button>
              {showUploadMenu && (
                <div className="absolute bottom-full left-0 mb-2 w-56 rounded-xl border bg-card/95 backdrop-blur-sm shadow-lg py-1.5 z-50 animate-scale-in">
                  <button
                    type="button"
                    onClick={() => { fileInputRef.current?.click(); setShowUploadMenu(false); }}
                    className="w-full px-4 py-2.5 text-left text-sm hover:bg-muted transition-colors flex items-center gap-2.5"
                  >
                    <Paperclip className="h-4 w-4 text-muted-foreground" />
                    {t.uploadPDF}
                  </button>
                  <div className="border-t my-1" />
                  <button
                    type="button"
                    onClick={() => {
                      setShowUploadMenu(false);
                      setSwarmPreset({ name: "auto", title: t.agentSwarm });
                      inputRef.current?.focus();
                    }}
                    className="w-full px-4 py-2.5 text-left text-sm hover:bg-muted transition-colors flex items-center gap-2.5"
                  >
                    <Users className="h-4 w-4 text-muted-foreground" />
                    {t.agentSwarm}
                  </button>
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.xlsx,.xls,.pptx,.csv,.tsv,.txt,.md,.log,.json,.yaml,.yml,.toml,.html,.xml,.rst,.png,.jpg,.jpeg,.gif,.bmp,.webp,.tiff"
              onChange={handleFileSelect}
              className="hidden"
            />
            <textarea
              ref={inputRef}
              value={input}
              rows={1}
              onChange={(e) => setInput(e.target.value)}
              onInput={(e) => {
                const el = e.target as HTMLTextAreaElement;
                el.style.height = "auto";
                el.style.height = el.scrollHeight + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  runPrompt(input.trim());
                }
              }}
              placeholder={t.prompt}
              className="flex-1 px-4 py-3 rounded-xl border bg-card text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-150 resize-none max-h-32 overflow-y-auto shadow-sm placeholder:text-muted-foreground/50"
              disabled={status === "streaming"}
            />
            {messages.length > 0 && (
              <button
                type="button"
                onClick={handleExport}
                className="w-10 h-10 rounded-xl border bg-card flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 hover:border-primary/30 transition-all duration-150 shrink-0 shadow-sm"
                title={t.exportChat}
              >
                <Download className="h-4.5 w-4.5" />
              </button>
            )}
            {status === "streaming" ? (
              <button
                type="button"
                onClick={handleCancel}
                className="h-10 px-4 rounded-xl bg-destructive text-destructive-foreground text-sm font-medium hover:brightness-110 transition-all duration-150 shrink-0 shadow-sm active:scale-[0.97]"
                title={t.stopGeneration}
              >
                <Square className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim() && !attachment}
                className="h-10 px-5 rounded-xl bg-primary text-primary-foreground text-sm font-medium disabled:opacity-40 hover:brightness-110 transition-all duration-150 shrink-0 shadow-sm active:scale-[0.97]"
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </form>
      </div>{/* end left chat area */}

      {/* Right: Watchlist + Examples sidebar */}
      <RightSidebar
        collapsed={rightPanelCollapsed}
        onToggle={toggleRightPanel}
        onAnalyze={runPrompt}
        onSelectExample={runPrompt}
      />
    </div>
  );
}
