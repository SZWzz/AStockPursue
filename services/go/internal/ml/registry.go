package ml

import (
	"context"
	"database/sql"
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// ModelRegistry persists ML models to a SQLite database.
type ModelRegistry struct {
	db *sql.DB
}

// NewModelRegistry creates a new ModelRegistry backed by the given database.
func NewModelRegistry(db *sql.DB) *ModelRegistry {
	return &ModelRegistry{db: db}
}

// Init creates the ml_models table if it does not already exist.
func (r *ModelRegistry) Init() error {
	_, err := r.db.Exec(`CREATE TABLE IF NOT EXISTS ml_models (
		id TEXT PRIMARY KEY,
		name TEXT NOT NULL,
		model_type TEXT NOT NULL,
		category TEXT NOT NULL,
		hyperparams TEXT NOT NULL DEFAULT '{}',
		metrics TEXT NOT NULL DEFAULT '{}',
		file_path TEXT NOT NULL DEFAULT '',
		file_bytes BLOB,
		status TEXT NOT NULL DEFAULT 'training',
		created_at INTEGER NOT NULL,
		updated_at INTEGER NOT NULL
	)`)
	return err
}

// Create inserts a new model into the registry. If the model's ID is empty, a
// new UUID is generated.
func (r *ModelRegistry) Create(ctx context.Context, model *MLModel) error {
	if model.ID == "" {
		model.ID = uuid.New().String()
	}
	now := time.Now().UTC()
	model.CreatedAt = now
	model.UpdatedAt = now
	if model.Status == "" {
		model.Status = StatusTraining
	}

	hpJSON, err := json.Marshal(model.Hyperparams)
	if err != nil {
		return err
	}
	mJSON, err := json.Marshal(model.Metrics)
	if err != nil {
		return err
	}

	_, err = r.db.ExecContext(ctx,
		`INSERT INTO ml_models (id, name, model_type, category, hyperparams, metrics, file_path, file_bytes, status, created_at, updated_at)
		 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		model.ID, model.Name, string(model.ModelType), string(model.Category),
		string(hpJSON), string(mJSON), model.FilePath, model.FileBytes,
		string(model.Status), model.CreatedAt.Unix(), model.UpdatedAt.Unix(),
	)
	return err
}

// Get retrieves a single model by its ID.
func (r *ModelRegistry) Get(ctx context.Context, id string) (*MLModel, error) {
	row := r.db.QueryRowContext(ctx,
		`SELECT id, name, model_type, category, hyperparams, metrics, file_path, file_bytes, status, created_at, updated_at
		 FROM ml_models WHERE id = ?`, id)

	model := &MLModel{}
	var hpJSON, mJSON string
	var createdAt, updatedAt int64
	err := row.Scan(&model.ID, &model.Name, &model.ModelType, &model.Category,
		&hpJSON, &mJSON, &model.FilePath, &model.FileBytes, &model.Status,
		&createdAt, &updatedAt)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	_ = json.Unmarshal([]byte(hpJSON), &model.Hyperparams)
	_ = json.Unmarshal([]byte(mJSON), &model.Metrics)
	model.CreatedAt = time.Unix(createdAt, 0).UTC()
	model.UpdatedAt = time.Unix(updatedAt, 0).UTC()
	return model, nil
}

// List returns all models matching the given category.
func (r *ModelRegistry) List(ctx context.Context, category ModelCategory) ([]*MLModel, error) {
	rows, err := r.db.QueryContext(ctx,
		`SELECT id, name, model_type, category, hyperparams, metrics, file_path, file_bytes, status, created_at, updated_at
		 FROM ml_models WHERE category = ? ORDER BY updated_at DESC`, string(category))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var models []*MLModel
	for rows.Next() {
		m := &MLModel{}
		var hpJSON, mJSON string
		var createdAt, updatedAt int64
		if err := rows.Scan(&m.ID, &m.Name, &m.ModelType, &m.Category,
			&hpJSON, &mJSON, &m.FilePath, &m.FileBytes, &m.Status,
			&createdAt, &updatedAt); err != nil {
			return nil, err
		}
		_ = json.Unmarshal([]byte(hpJSON), &m.Hyperparams)
		_ = json.Unmarshal([]byte(mJSON), &m.Metrics)
		m.CreatedAt = time.Unix(createdAt, 0).UTC()
		m.UpdatedAt = time.Unix(updatedAt, 0).UTC()
		models = append(models, m)
	}
	return models, rows.Err()
}

// ListByStatus returns all models with the given lifecycle status.
func (r *ModelRegistry) ListByStatus(ctx context.Context, status ModelStatus) ([]*MLModel, error) {
	rows, err := r.db.QueryContext(ctx,
		`SELECT id, name, model_type, category, hyperparams, metrics, file_path, file_bytes, status, created_at, updated_at
		 FROM ml_models WHERE status = ? ORDER BY updated_at DESC`, string(status))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var models []*MLModel
	for rows.Next() {
		m := &MLModel{}
		var hpJSON, mJSON string
		var createdAt, updatedAt int64
		if err := rows.Scan(&m.ID, &m.Name, &m.ModelType, &m.Category,
			&hpJSON, &mJSON, &m.FilePath, &m.FileBytes, &m.Status,
			&createdAt, &updatedAt); err != nil {
			return nil, err
		}
		_ = json.Unmarshal([]byte(hpJSON), &m.Hyperparams)
		_ = json.Unmarshal([]byte(mJSON), &m.Metrics)
		m.CreatedAt = time.Unix(createdAt, 0).UTC()
		m.UpdatedAt = time.Unix(updatedAt, 0).UTC()
		models = append(models, m)
	}
	return models, rows.Err()
}

// UpdateMetrics replaces the metrics map for the model identified by id.
func (r *ModelRegistry) UpdateMetrics(ctx context.Context, id string, metrics map[string]float64) error {
	mJSON, err := json.Marshal(metrics)
	if err != nil {
		return err
	}
	_, err = r.db.ExecContext(ctx,
		`UPDATE ml_models SET metrics = ?, updated_at = ? WHERE id = ?`,
		string(mJSON), time.Now().UTC().Unix(), id)
	return err
}

// Archive sets the model status to archived and updates the timestamp.
func (r *ModelRegistry) Archive(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx,
		`UPDATE ml_models SET status = ?, updated_at = ? WHERE id = ?`,
		string(StatusArchived), time.Now().UTC().Unix(), id)
	return err
}
