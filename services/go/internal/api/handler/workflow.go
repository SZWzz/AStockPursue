package handler

import (
	"context"
	"net/http"
	"strconv"
	"time"

	workflowv1 "github.com/astockpursue/go-core/internal/gen/workflow/v1"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// WorkflowRecord represents a workflow stored in PostgreSQL.
type WorkflowRecord struct {
	ID        int    `json:"id"`
	Name      string `json:"name"`
	Nodes     string `json:"nodes"`
	Edges     string `json:"edges"`
	CreatedAt string `json:"created_at"`
}

// WorkflowHandler proxies workflow execution requests to Python WorkflowService via gRPC.
type WorkflowHandler struct {
	client workflowv1.WorkflowServiceClient
	db     *pgxpool.Pool
}

// NewWorkflowHandler creates a new WorkflowHandler.
func NewWorkflowHandler(client workflowv1.WorkflowServiceClient, db *pgxpool.Pool) *WorkflowHandler {
	return &WorkflowHandler{client: client, db: db}
}

func (h *WorkflowHandler) grpcUnavailable(c *gin.Context) {
	c.JSON(http.StatusServiceUnavailable, gin.H{
		"error":   "Python gRPC service is not running",
		"message": "Start the Python research layer: cd services/python && python -m src.grpc.server",
	})
}

// ListWorkflows returns all saved workflows from PostgreSQL.
// GET /api/v1/workflow
func (h *WorkflowHandler) ListWorkflows(c *gin.Context) {
	if h.db == nil {
		c.JSON(http.StatusOK, gin.H{"workflows": []WorkflowRecord{}})
		return
	}

	rows, err := h.db.Query(c.Request.Context(),
		`SELECT id, name, nodes, edges, created_at
		 FROM workflows ORDER BY updated_at DESC`)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	workflows := make([]WorkflowRecord, 0)
	for rows.Next() {
		var w WorkflowRecord
		var createdAt time.Time
		if err := rows.Scan(&w.ID, &w.Name, &w.Nodes, &w.Edges, &createdAt); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		w.CreatedAt = createdAt.Format(time.RFC3339)
		workflows = append(workflows, w)
	}

	c.JSON(http.StatusOK, gin.H{"workflows": workflows})
}

// SaveWorkflow creates or updates a workflow.
// POST /api/v1/workflow
func (h *WorkflowHandler) SaveWorkflow(c *gin.Context) {
	var req struct {
		ID    string `json:"id"`
		Name  string `json:"name"`
		Nodes string `json:"nodes"`
		Edges string `json:"edges"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Name == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "name required"})
		return
	}

	if h.db == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "database not available"})
		return
	}

	// Try to update if ID is provided and exists
	if req.ID != "" {
		id, err := strconv.Atoi(req.ID)
		if err == nil {
			tag, err := h.db.Exec(c.Request.Context(),
				`UPDATE workflows SET name = $1, nodes = $2, edges = $3, updated_at = now() WHERE id = $4`,
				req.Name, req.Nodes, req.Edges, id)
			if err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
				return
			}
			if tag.RowsAffected() > 0 {
				c.JSON(http.StatusOK, gin.H{"workflow": WorkflowRecord{
					ID: id, Name: req.Name, Nodes: req.Nodes, Edges: req.Edges,
					CreatedAt: time.Now().Format(time.RFC3339),
				}})
				return
			}
		}
	}

	// Insert new workflow
	var newID int
	err := h.db.QueryRow(c.Request.Context(),
		`INSERT INTO workflows (name, nodes, edges) VALUES ($1, $2, $3) RETURNING id`,
		req.Name, req.Nodes, req.Edges).Scan(&newID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"workflow": WorkflowRecord{
		ID: newID, Name: req.Name, Nodes: req.Nodes, Edges: req.Edges,
		CreatedAt: time.Now().Format(time.RFC3339),
	}})
}

// ExecuteWorkflow runs a workflow by ID.
// POST /api/v1/workflow/execute
func (h *WorkflowHandler) ExecuteWorkflow(c *gin.Context) {
	if h.client == nil {
		h.grpcUnavailable(c)
		return
	}
	var req struct {
		WorkflowID string            `json:"workflow_id" binding:"required"`
		Params     map[string]string `json:"params"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Minute)
	defer cancel()

	pbReq := &workflowv1.WorkflowRequest{
		WorkflowId: req.WorkflowID,
		Params:     req.Params,
	}

	resp, err := h.client.ExecuteWorkflow(ctx, pbReq)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"workflow_id": req.WorkflowID,
		"status":      resp.Status,
		"error":       resp.Error,
	})
}

// GetNodeResult returns the result of a specific node.
// GET /api/v1/workflow/node/:id?workflow_id=xxx
func (h *WorkflowHandler) GetNodeResult(c *gin.Context) {
	if h.client == nil {
		h.grpcUnavailable(c)
		return
	}
	nodeID := c.Param("id")
	workflowID := c.Query("workflow_id")

	if workflowID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "workflow_id query param required"})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 10*time.Second)
	defer cancel()

	pbReq := &workflowv1.NodeQuery{
		WorkflowId: workflowID,
		NodeId:     nodeID,
	}

	resp, err := h.client.GetNodeResult(ctx, pbReq)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if resp.Error != "" {
		c.JSON(http.StatusNotFound, gin.H{"error": resp.Error})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"node_id":    resp.NodeId,
		"output":     string(resp.Output),
		"output_len": len(resp.Output),
	})
}

// RunWorkflow starts execution of a workflow by ID with a specified mode.
// POST /api/v1/workflow/:id/run
func (h *WorkflowHandler) RunWorkflow(c *gin.Context) {
	if h.client == nil {
		h.grpcUnavailable(c)
		return
	}

	workflowID := c.Param("id")
	if workflowID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "id is required"})
		return
	}

	mode := c.DefaultQuery("mode", "backtest")
	switch mode {
	case "backtest", "paper", "live":
		// valid modes
	default:
		c.JSON(http.StatusBadRequest, gin.H{"error": "mode must be one of: backtest, paper, live"})
		return
	}

	var req struct {
		Params map[string]string `json:"params"`
	}
	if c.Request.Body != nil {
		_ = c.ShouldBindJSON(&req)
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Minute)
	defer cancel()

	pbReq := &workflowv1.WorkflowRequest{
		WorkflowId: workflowID,
		Params:     req.Params,
	}

	// Add mode to params if not already present
	if pbReq.Params == nil {
		pbReq.Params = make(map[string]string)
	}
	pbReq.Params["mode"] = mode

	resp, err := h.client.ExecuteWorkflow(ctx, pbReq)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"workflow_id": workflowID,
		"mode":        mode,
		"status":      resp.Status,
		"error":       resp.Error,
	})
}
