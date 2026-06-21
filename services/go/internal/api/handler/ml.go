package handler

import (
	"context"
	"net/http"
	"time"

	"github.com/astockpursue/go-core/internal/ml"
	"github.com/gin-gonic/gin"
)

// MLHandler exposes HTTP endpoints for managing ML models in the registry.
type MLHandler struct {
	registry *ml.ModelRegistry
}

// NewMLHandler creates an MLHandler backed by the given ModelRegistry.
func NewMLHandler(registry *ml.ModelRegistry) *MLHandler {
	return &MLHandler{registry: registry}
}

// ── Request / response types ────────────────────────────────────────

type createModelRequest struct {
	Name        string         `json:"name" binding:"required"`
	ModelType   ml.ModelType   `json:"model_type" binding:"required"`
	Category    ml.ModelCategory `json:"category" binding:"required"`
	Hyperparams map[string]any `json:"hyperparams"`
	Metrics     map[string]float64 `json:"metrics"`
	FilePath    string         `json:"file_path"`
	FileBytes   []byte         `json:"file_bytes"`
	Status      ml.ModelStatus `json:"status"`
}

type modelResponse struct {
	ID          string             `json:"id"`
	Name        string             `json:"name"`
	ModelType   ml.ModelType       `json:"model_type"`
	Category    ml.ModelCategory   `json:"category"`
	Hyperparams map[string]any     `json:"hyperparams"`
	Metrics     map[string]float64 `json:"metrics"`
	FilePath    string             `json:"file_path"`
	Status      ml.ModelStatus     `json:"status"`
	CreatedAt   string             `json:"created_at"`
	UpdatedAt   string             `json:"updated_at"`
}

func modelToResponse(m *ml.MLModel) modelResponse {
	return modelResponse{
		ID:          m.ID,
		Name:        m.Name,
		ModelType:   m.ModelType,
		Category:    m.Category,
		Hyperparams: m.Hyperparams,
		Metrics:     m.Metrics,
		FilePath:    m.FilePath,
		Status:      m.Status,
		CreatedAt:   m.CreatedAt.Format(time.RFC3339),
		UpdatedAt:   m.UpdatedAt.Format(time.RFC3339),
	}
}

// ── Handlers ────────────────────────────────────────────────────────

// ListModels returns all models, optionally filtered by category and/or status.
//
//	GET /api/v1/ml/models?category=factor&status=ready
func (h *MLHandler) ListModels(c *gin.Context) {
	category := c.Query("category")
	status := c.Query("status")

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	var models []*ml.MLModel
	var err error

	if status != "" {
		models, err = h.registry.ListByStatus(ctx, ml.ModelStatus(status))
	} else if category != "" {
		models, err = h.registry.List(ctx, ml.ModelCategory(category))
	} else {
		// List all categories
		for _, cat := range []ml.ModelCategory{ml.CategoryFactor, ml.CategorySignal, ml.CategoryRisk} {
			catModels, catErr := h.registry.List(ctx, cat)
			if catErr != nil {
				err = catErr
				break
			}
			models = append(models, catModels...)
		}
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if models == nil {
		models = []*ml.MLModel{}
	}

	response := make([]modelResponse, len(models))
	for i, m := range models {
		response[i] = modelToResponse(m)
	}

	c.JSON(http.StatusOK, gin.H{
		"models": response,
		"count":  len(response),
	})
}

// CreateModel registers a new ML model.
//
//	POST /api/v1/ml/models
func (h *MLHandler) CreateModel(c *gin.Context) {
	var req createModelRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Hyperparams == nil {
		req.Hyperparams = make(map[string]any)
	}
	if req.Metrics == nil {
		req.Metrics = make(map[string]float64)
	}

	model := &ml.MLModel{
		Name:        req.Name,
		ModelType:   req.ModelType,
		Category:    req.Category,
		Hyperparams: req.Hyperparams,
		Metrics:     req.Metrics,
		FilePath:    req.FilePath,
		FileBytes:   req.FileBytes,
		Status:      req.Status,
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	if err := h.registry.Create(ctx, model); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"model": modelToResponse(model),
	})
}

// GetModel retrieves a single model by its ID.
//
//	GET /api/v1/ml/models/:id
func (h *MLHandler) GetModel(c *gin.Context) {
	id := c.Param("id")

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	model, err := h.registry.Get(ctx, id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if model == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "model not found: " + id})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"model": modelToResponse(model),
	})
}

// ArchiveModel sets a model's status to archived.
//
//	POST /api/v1/ml/models/:id/archive
func (h *MLHandler) ArchiveModel(c *gin.Context) {
	id := c.Param("id")

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	if err := h.registry.Archive(ctx, id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "model archived",
		"id":      id,
	})
}

// TrainModel starts training for the specified model.
//
//	POST /api/v1/ml/models/:id/train
func (h *MLHandler) TrainModel(c *gin.Context) {
	id := c.Param("id")

	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	model, err := h.registry.Get(ctx, id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if model == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "model not found"})
		return
	}

	// Set status to training (in-memory for now).
	model.Status = ml.ModelStatus("training")

	// Launch training in background
	go func(m *ml.MLModel) {
		// Simulate training with a sleep. In production, this calls Python gRPC.
		time.Sleep(2 * time.Second)
		m.Status = ml.ModelStatus("ready")
		// TODO: Train the model with actual data later
	}(model)

	c.JSON(http.StatusOK, gin.H{"status": "training_started", "id": id})
}
