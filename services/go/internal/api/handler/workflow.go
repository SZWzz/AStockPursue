package handler

import (
	"context"
	"net/http"
	"sync"
	"time"

	workflowv1 "github.com/astockpursue/go-core/internal/gen/workflow/v1"
	"github.com/gin-gonic/gin"
)

// WorkflowHandler proxies workflow execution requests to Python WorkflowService via gRPC.
type WorkflowHandler struct {
	client workflowv1.WorkflowServiceClient
	mu     sync.RWMutex
	store  []WorkflowRecord // in-memory workflow list (fallback when gRPC is down)
}

// WorkflowRecord is a lightweight workflow entry stored in memory.
type WorkflowRecord struct {
	ID        string `json:"id"`
	Name      string `json:"name"`
	Nodes     string `json:"nodes"`  // JSON string of nodes
	Edges     string `json:"edges"`  // JSON string of edges
	Status    string `json:"status"`
	UpdatedAt string `json:"updated_at"`
}

// NewWorkflowHandler creates a new WorkflowHandler.
func NewWorkflowHandler(client workflowv1.WorkflowServiceClient) *WorkflowHandler {
	return &WorkflowHandler{client: client, store: make([]WorkflowRecord, 0)}
}

func (h *WorkflowHandler) grpcUnavailable(c *gin.Context) {
	c.JSON(http.StatusServiceUnavailable, gin.H{
		"error":   "Python gRPC service is not running",
		"message": "Start the Python research layer: cd services/python && python -m src.grpc.server",
	})
}

// ListWorkflows returns all saved workflows (in-memory store).
// GET /api/v1/workflow
func (h *WorkflowHandler) ListWorkflows(c *gin.Context) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	c.JSON(http.StatusOK, gin.H{"workflows": h.store})
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

	h.mu.Lock()
	defer h.mu.Unlock()

	// Update existing or append new
	for i, w := range h.store {
		if w.ID == req.ID {
			h.store[i].Name = req.Name
			h.store[i].Nodes = req.Nodes
			h.store[i].Edges = req.Edges
			h.store[i].UpdatedAt = time.Now().Format(time.RFC3339)
			c.JSON(http.StatusOK, gin.H{"workflow": h.store[i]})
			return
		}
	}

	record := WorkflowRecord{
		ID:        req.ID,
		Name:      req.Name,
		Nodes:     req.Nodes,
		Edges:     req.Edges,
		Status:    "draft",
		UpdatedAt: time.Now().Format(time.RFC3339),
	}
	h.store = append(h.store, record)
	c.JSON(http.StatusCreated, gin.H{"workflow": record})
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

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
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

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
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
