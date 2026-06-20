package handler

import (
	"context"
	"net/http"
	"time"

	workflowv1 "github.com/astockpursue/go-core/internal/gen/workflow/v1"
	"github.com/gin-gonic/gin"
)

// WorkflowHandler proxies workflow execution requests to Python WorkflowService via gRPC.
type WorkflowHandler struct {
	client workflowv1.WorkflowServiceClient
}

// NewWorkflowHandler creates a new WorkflowHandler.
func NewWorkflowHandler(client workflowv1.WorkflowServiceClient) *WorkflowHandler {
	return &WorkflowHandler{client: client}
}

// ExecuteWorkflow runs a workflow by ID.
// POST /api/v1/workflow/execute
func (h *WorkflowHandler) ExecuteWorkflow(c *gin.Context) {
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
