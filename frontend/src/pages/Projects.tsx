/**
 * Projects — top-level dashboard for research projects.
 *
 * Lists all projects, shows workflow counts, and allows creating/opening projects.
 * Each project card links to its first workflow or creates a new one.
 *
 * Route: /projects
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, FolderOpen, Workflow, Trash2, ArrowRight, Copy, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState } from "@/components/common/EmptyState";

interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  workflow_count?: number;
  created_at: string;
  updated_at: string;
}

export default function Projects() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [showTemplates, setShowTemplates] = useState(false);
  const [templates, setTemplates] = useState<any[]>([]);
  const [selectedProjectForTemplate, setSelectedProjectForTemplate] = useState<string>("");

  const loadTemplates = async () => {
    try {
      const data = await api.listTemplates();
      if (Array.isArray(data)) setTemplates(data);
    } catch {}
  };

  const instantiateTemplate = async (templateId: string, templateName: string) => {
    const projectId = selectedProjectForTemplate || projects[0]?.id;
    if (!projectId) {
      // Create a default project first
      try {
        const p = await api.createProject({ name: (t as any).projMyResearch });
        const data = await api.instantiateTemplate(templateId, { project_id: (p as any).id, name: templateName });
        navigate(`/workflow/${(p as any).id}/${(data as any).id}`);
      } catch (e: any) {
        setError(e.message || (t as any).projFailedCreateForTemplate);
      }
      return;
    }
    try {
      const data = await api.instantiateTemplate(templateId, { project_id: projectId, name: templateName });
      navigate(`/workflow/${projectId}/${(data as any).id}`);
    } catch (e: any) {
      setError(e.message || (t as any).projFailedTemplate);
    }
  };

  const loadProjects = async () => {
    setLoading(true);
    try {
      const data = await api.listProjects();
      const list = Array.isArray(data) ? data : [];

      // Fetch workflow counts per project
      const enriched = await Promise.all(
        list.map(async (p: Project) => {
          try {
            const wfs = await api.listWorkflows(p.id);
            return { ...p, workflow_count: Array.isArray(wfs) ? wfs.length : 0 };
          } catch {
            return { ...p, workflow_count: 0 };
          }
        })
      );
      setProjects(enriched);
    } catch (e: any) {
      setError(e.message || (t as any).projFailedLoad);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadProjects(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      await api.createProject({ name: newName.trim(), description: newDesc.trim() });
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      await loadProjects();
    } catch (e: any) {
      setError(e.message || (t as any).projFailedCreate);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm((t as any).projArchiveConfirm)) return;
    try {
      await api.deleteProject(id);
      await loadProjects();
    } catch (e: any) {
      setError(e.message || (t as any).projFailedArchive);
    }
  };

  const handleOpenProject = async (project: Project) => {
    if (project.workflow_count && project.workflow_count > 0) {
      // Open the first workflow in the project
      try {
        const wfs = await api.listWorkflows(project.id);
        if (Array.isArray(wfs) && wfs.length > 0) {
          navigate(`/workflow/${project.id}/${wfs[0].id}`);
          return;
        }
      } catch {}
    }
    // No workflows yet — create one
    navigate(`/workflow/${project.id}/new?new=true`);
  };

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <p className="text-muted-foreground">{(t as any).projLoading}</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6 page-enter-stagger">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{(t as any).projTitle}</h1>
          <p className="text-sm text-muted-foreground mt-1">{(t as any).projSubtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setShowTemplates(!showTemplates); loadTemplates(); }}
            className="btn btn-outline btn-sm"
          >
            <Zap className="h-4 w-4" />
            {(t as any).projTemplates}
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="btn btn-primary btn-sm"
          >
            <Plus className="h-4 w-4" />
            {(t as any).projNewProject}
          </button>
        </div>
      </div>

      {error && (
        <div className="message-bar error rounded-lg">{error}</div>
      )}

      {/* Template gallery */}
      {showTemplates && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">{(t as any).projStartFromTemplate}</h3>
            {projects.length > 0 && (
              <select
                value={selectedProjectForTemplate}
                onChange={(e) => setSelectedProjectForTemplate(e.target.value)}
                className="text-xs px-2 py-1 rounded border bg-background"
              >
                <option value="">{(t as any).projAutoCreate}</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {templates.map((t: any) => (
              <div key={t.id} className="flex items-start justify-between p-3 rounded-lg border bg-muted/30 hover:border-primary/50 transition-colors">
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-medium">{t.name}</h4>
                  <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{t.description}</p>
                  <span className="text-[10px] text-muted-foreground mt-1 block">
                    {t.node_count} {(t as any).projNodes} · {t.category}
                  </span>
                </div>
                <button
                  onClick={() => instantiateTemplate(t.id, t.name)}
                  className="btn btn-primary btn-sm ml-3 shrink-0"
                >
                  <Copy className="h-3 w-3" />
                  {(t as any).projUse}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create dialog */}
      {showCreate && (
        <div className="card p-4 space-y-3">
          <h3 className="font-semibold">{(t as any).projNewResearchProject}</h3>
          <input
            type="text"
            placeholder={(t as any).projProjectName}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="input"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <input
            type="text"
            placeholder={(t as any).projDescOptional}
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="input"
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowCreate(false)} className="btn btn-ghost btn-sm">{(t as any).projCancel}</button>
            <button onClick={handleCreate} disabled={!newName.trim()} className="btn btn-primary btn-sm">{(t as any).projCreate}</button>
          </div>
        </div>
      )}

      {/* Project grid */}
      {projects.length === 0 ? (
        <EmptyState
          icon={<FolderOpen className="h-12 w-12" />}
          title={(t as any).projNoProjects || "No projects yet"}
          description={(t as any).projNoProjectsHint || "Create your first research project to get started"}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <div
              key={p.id}
              onClick={() => handleOpenProject(p)}
              className="group cursor-pointer card-hover p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <FolderOpen className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold text-sm truncate max-w-[180px]">{p.name}</h3>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(p.id); }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-muted-foreground hover:text-red-500 rounded transition-all"
                  title={(t as any).projArchive}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
              {p.description && (
                <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{p.description}</p>
              )}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Workflow className="h-3 w-3" />
                  <span>{p.workflow_count ?? 0} {(p.workflow_count ?? 0) !== 1 ? (t as any).projWorkflows : (t as any).projWorkflow}</span>
                </div>
                <span className="flex items-center gap-1 text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                  Open <ArrowRight className="h-3 w-3" />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
