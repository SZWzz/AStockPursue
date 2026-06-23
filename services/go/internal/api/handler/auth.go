package handler

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"hash/fnv"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/astockpursue/go-core/internal/log"
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/pbkdf2"
)

// JWT secret key — reads from JWT_SECRET env, with dev fallback.
// If unset and not in dev mode, the first handler call will fatal.
var jwtSecret []byte
var pkgLogger = log.New()

func init() {
	if s := os.Getenv("JWT_SECRET"); s != "" {
		jwtSecret = []byte(s)
	} else if os.Getenv("GO_ENV") == "development" {
		jwtSecret = []byte("astockpursue-dev-secret-not-for-production")
	}
}

type userRecord struct {
	Username string
	Password string // PBKDF2 hashed
}

// RateLimiter is a simple in-memory rate limiter.
type RateLimiter struct {
	mu       sync.Mutex
	attempts map[string][]time.Time
	window   time.Duration
	max      int
}

// NewRateLimiter creates a rate limiter with the given window and max attempts.
func NewRateLimiter(window time.Duration, max int) *RateLimiter {
	return &RateLimiter{
		attempts: make(map[string][]time.Time),
		window:   window,
		max:      max,
	}
}

// Allow returns true if the key is within limits, false if rate limit exceeded.
func (rl *RateLimiter) Allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	cutoff := now.Add(-rl.window)

	// Filter to keep only attempts within the window
	filtered := rl.attempts[key][:0]
	for _, t := range rl.attempts[key] {
		if t.After(cutoff) {
			filtered = append(filtered, t)
		}
	}
	rl.attempts[key] = filtered

	if len(filtered) >= rl.max {
		return false
	}

	rl.attempts[key] = append(rl.attempts[key], now)
	return true
}

// User represents a user persisted in the database.
type User struct {
	Username     string
	PasswordHash string
	Salt         string
}

// UserRepository abstracts persistent user storage.
type UserRepository interface {
	FindByUsername(ctx context.Context, username string) (*User, error)
	Save(ctx context.Context, user *User) error
}

// pgUserRepository implements UserRepository backed by PostgreSQL.
type pgUserRepository struct {
	db *pgxpool.Pool
}

// NewUserRepository creates a PostgreSQL-backed UserRepository.
func NewUserRepository(db *pgxpool.Pool) UserRepository {
	if db == nil {
		return nil
	}
	return &pgUserRepository{db: db}
}

func (r *pgUserRepository) FindByUsername(ctx context.Context, username string) (*User, error) {
	var u User
	err := r.db.QueryRow(ctx,
		"SELECT username, password_hash, salt FROM users WHERE username = $1", username,
	).Scan(&u.Username, &u.PasswordHash, &u.Salt)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	return &u, err
}

func (r *pgUserRepository) Save(ctx context.Context, user *User) error {
	_, err := r.db.Exec(ctx,
		"INSERT INTO users (username, password_hash, salt) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
		user.Username, user.PasswordHash, user.Salt,
	)
	return err
}

// AuthHandler provides registration and login endpoints.
// Uses a PostgreSQL-backed UserRepository when available; falls back to in-memory.
type AuthHandler struct {
	mu         sync.RWMutex
	users      map[string]*userRecord
	userRepo   UserRepository
	logger     *log.Logger
	regLimiter *RateLimiter // 5 attempts per minute per IP
	loginLimiter *RateLimiter // 5 attempts per minute per username
}

// NewAuthHandler creates an AuthHandler with an optional UserRepository.
// When userRepo is nil, in-memory storage is used as fallback.
func NewAuthHandler(userRepo UserRepository) *AuthHandler {
	h := &AuthHandler{
		users:        make(map[string]*userRecord),
		userRepo:     userRepo,
		logger:       log.New(),
		regLimiter:   NewRateLimiter(time.Minute, 5),
		loginLimiter: NewRateLimiter(time.Minute, 5),
	}
	h.initAdminUser()
	return h
}

// initAdminUser creates the admin user if ADMIN_PASSWORD environment variable
// is set and no admin user already exists.
func (h *AuthHandler) initAdminUser() {
	adminPass := os.Getenv("ADMIN_PASSWORD")
	if adminPass == "" {
		return
	}

	// Check if admin already exists
	h.mu.RLock()
	_, exists := h.users["admin"]
	h.mu.RUnlock()
	if exists {
		return
	}
	if h.userRepo != nil {
		if _, err := h.userRepo.FindByUsername(context.Background(), "admin"); err == nil {
			return // admin exists in PG
		}
	}

	h.mu.Lock()
	h.users["admin"] = &userRecord{
		Username: "admin",
		Password: hashPassword(adminPass),
	}
	h.mu.Unlock()
	h.logger.Info("admin user initialized from ADMIN_PASSWORD")
}

// Register creates a new user account.
// POST /api/v1/auth/register
func (h *AuthHandler) Register(c *gin.Context) {
	var req struct {
		Username string `json:"username" binding:"required"`
		Password string `json:"password" binding:"required,min=6"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Rate limit: 5 attempts per minute per IP
	clientIP := c.ClientIP()
	if !h.regLimiter.Allow(clientIP) {
		c.JSON(http.StatusTooManyRequests, gin.H{"error": "too many registration attempts, try again later"})
		return
	}

	// Try PG-backed repository first
	if h.userRepo != nil {
		existing, err := h.userRepo.FindByUsername(c.Request.Context(), req.Username)
		if err != nil {
			h.logger.Error("auth: FindByUsername error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
			return
		}
		if existing != nil {
			c.JSON(http.StatusConflict, gin.H{"error": "username already exists"})
			return
		}
		salt := make([]byte, 16)
		_, _ = rand.Read(salt)
		hash := pbkdf2.Key([]byte(req.Password), salt, 100000, 32, sha256.New)
		user := &User{
			Username:     req.Username,
			PasswordHash: hex.EncodeToString(hash),
			Salt:         hex.EncodeToString(salt),
		}
		if err := h.userRepo.Save(c.Request.Context(), user); err != nil {
			h.logger.Error("auth: Save error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to persist user"})
			return
		}
		token, err := generateToken(req.Username)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to generate token"})
			return
		}
		c.JSON(http.StatusCreated, gin.H{"token": token, "username": req.Username})
		return
	}

	// Fallback to in-memory
	h.mu.Lock()
	defer h.mu.Unlock()

	if _, exists := h.users[req.Username]; exists {
		c.JSON(http.StatusConflict, gin.H{"error": "username already exists"})
		return
	}

	h.users[req.Username] = &userRecord{
		Username: req.Username,
		Password: hashPassword(req.Password),
	}

	token, err := generateToken(req.Username)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to generate token"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"token": token, "username": req.Username})
}

// Login authenticates a user and returns a JWT token.
// POST /api/v1/auth/login
func (h *AuthHandler) Login(c *gin.Context) {
	var req struct {
		Username string `json:"username" binding:"required"`
		Password string `json:"password" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Rate limit: 5 attempts per minute per username
	if !h.loginLimiter.Allow(req.Username) {
		c.JSON(http.StatusTooManyRequests, gin.H{"error": "too many login attempts, try again later"})
		return
	}

	// Try PG-backed repository first
	if h.userRepo != nil {
		user, err := h.userRepo.FindByUsername(c.Request.Context(), req.Username)
		if err != nil {
			h.logger.Error("auth: FindByUsername error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
			return
		}
		if user == nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid credentials"})
			return
		}
		salt, err := hex.DecodeString(user.Salt)
		if err != nil {
			h.logger.Error("auth: failed to decode salt hex: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
			return
		}
		expectedHash, err := hex.DecodeString(user.PasswordHash)
		if err != nil {
			h.logger.Error("auth: failed to decode password hash hex: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
			return
		}
		actualHash := pbkdf2.Key([]byte(req.Password), salt, 100000, 32, sha256.New)
		if hex.EncodeToString(actualHash) != hex.EncodeToString(expectedHash) {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid credentials"})
			return
		}
		token, err := generateToken(req.Username)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to generate token"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"token": token, "username": req.Username})
		return
	}

	// Fallback to in-memory
	h.mu.RLock()
	user, exists := h.users[req.Username]
	h.mu.RUnlock()

	if !exists || !verifyPassword(req.Password, user.Password) {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid credentials"})
		return
	}

	token, err := generateToken(req.Username)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to generate token"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"token": token, "username": req.Username})
}

// AdminSetup creates the admin user. Only succeeds if no admin exists.
// POST /api/v1/admin/setup
func (h *AuthHandler) AdminSetup(c *gin.Context) {
	var req struct {
		Password string `json:"password" binding:"required,min=8"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Check if admin already exists
	h.mu.RLock()
	if _, exists := h.users["admin"]; exists {
		h.mu.RUnlock()
		c.JSON(http.StatusConflict, gin.H{"error": "admin user already exists"})
		return
	}
	h.mu.RUnlock()

	if h.userRepo != nil {
		if _, err := h.userRepo.FindByUsername(c.Request.Context(), "admin"); err == nil {
			c.JSON(http.StatusConflict, gin.H{"error": "admin user already exists"})
			return
		}
	}

	h.mu.Lock()
	h.users["admin"] = &userRecord{
		Username: "admin",
		Password: hashPassword(req.Password),
	}
	h.mu.Unlock()

	h.logger.Info("admin user created via setup endpoint")
	c.JSON(http.StatusCreated, gin.H{"status": "admin_created"})
}

// ── Helpers ───────────────────────────────────────────────────────

func hashPassword(password string) string {
	salt := make([]byte, 16)
	_, _ = rand.Read(salt)
	hash := pbkdf2.Key([]byte(password), salt, 100000, 32, sha256.New)
	return hex.EncodeToString(salt) + ":" + hex.EncodeToString(hash)
}

func verifyPassword(password, stored string) bool {
	parts := split(stored, ":")
	if len(parts) != 2 {
		return false
	}
	salt, err := hex.DecodeString(parts[0])
	if err != nil {
		return false
	}
	expectedHash, err := hex.DecodeString(parts[1])
	if err != nil {
		return false
	}
	actualHash := pbkdf2.Key([]byte(password), salt, 100000, 32, sha256.New)
	return hex.EncodeToString(actualHash) == hex.EncodeToString(expectedHash)
}

// usernameToID generates a deterministic numeric user ID from a username.
// Uses FNV-1a hash for simplicity and speed — this is not a security-critical
// hash, just a way to turn usernames into stable numeric IDs for DB queries.
func usernameToID(username string) int {
	h := fnv.New32a()
	h.Write([]byte(username))
	return int(h.Sum32())
}

func generateToken(username string) (string, error) {
	if len(jwtSecret) == 0 {
		pkgLogger.Error("JWT_SECRET environment variable is required")
		return "", fmt.Errorf("JWT_SECRET environment variable is required")
	}
	claims := jwt.MapClaims{
		"sub":     username,
		"user_id": strconv.Itoa(usernameToID(username)),
		"iat":     time.Now().Unix(),
		"exp":     time.Now().Add(24 * time.Hour).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(jwtSecret)
}

// ValidateToken parses and validates a JWT token string.
func ValidateToken(tokenStr string) (string, error) {
	if len(jwtSecret) == 0 {
		pkgLogger.Error("JWT_SECRET environment variable is required")
		return "", fmt.Errorf("JWT_SECRET environment variable is required")
	}
	token, err := jwt.Parse(tokenStr, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return jwtSecret, nil
	})
	if err != nil {
		return "", err
	}
	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok || !token.Valid {
		return "", fmt.Errorf("invalid token")
	}
	sub, _ := claims["sub"].(string)
	return sub, nil
}

// ValidateTokenWithID parses a JWT token and returns username and user_id.
func ValidateTokenWithID(tokenStr string) (string, int, error) {
	if len(jwtSecret) == 0 {
		pkgLogger.Error("JWT_SECRET environment variable is required")
		return "", 0, fmt.Errorf("JWT_SECRET environment variable is required")
	}
	token, err := jwt.Parse(tokenStr, func(t *jwt.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return jwtSecret, nil
	})
	if err != nil {
		return "", 0, err
	}
	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok || !token.Valid {
		return "", 0, fmt.Errorf("invalid token")
	}
	sub, _ := claims["sub"].(string)
	userID := 0
	if uidStr, ok := claims["user_id"].(string); ok {
		if uid, err := strconv.Atoi(uidStr); err == nil {
			userID = uid
		}
	}
	return sub, userID, nil
}

func split(s, sep string) []string {
	var result []string
	for i := 0; i < len(s); {
		j := i
		for j < len(s) && s[j:j+1] != sep {
			j++
		}
		result = append(result, s[i:j])
		i = j + len(sep)
		if j == len(s) {
			break
		}
	}
	return result
}
