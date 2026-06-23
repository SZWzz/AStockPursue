package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/astockpursue/go-core/internal/notify"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
)

func TestGetSubscriptionStatus_Unauthenticated(t *testing.T) {
	gin.SetMode(gin.TestMode)

	h := NewSignalPushHandler(nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("GET", "/api/v1/signals/subscription/status", nil)

	h.GetSubscriptionStatus(c)

	assert.Equal(t, http.StatusUnauthorized, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "authentication required", resp["error"])
}

func TestGetSubscriptionStatus_NilDB(t *testing.T) {
	gin.SetMode(gin.TestMode)

	h := NewSignalPushHandler(nil, nil)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("GET", "/api/v1/signals/subscription/status", nil)

	h.GetSubscriptionStatus(c)

	assert.Equal(t, http.StatusServiceUnavailable, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	assert.NoError(t, err)
	assert.Equal(t, "database unavailable", resp["error"])
}

func TestUpdateSubscription_Validation(t *testing.T) {
	gin.SetMode(gin.TestMode)

	h := NewSignalPushHandler(nil, nil)

	t.Run("unauthenticated returns 401", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("PUT", "/api/v1/signals/subscription",
			strings.NewReader(`{"enabled":true,"channels":{"telegram":{}}}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.UpdateSubscription(c)

		assert.Equal(t, http.StatusUnauthorized, w.Code)

		var resp map[string]string
		err := json.Unmarshal(w.Body.Bytes(), &resp)
		assert.NoError(t, err)
		assert.Equal(t, "authentication required", resp["error"])
	})

	t.Run("invalid json returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("PUT", "/api/v1/signals/subscription",
			strings.NewReader(`{invalid}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.UpdateSubscription(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})

	t.Run("nil db returns 503", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("PUT", "/api/v1/signals/subscription",
			strings.NewReader(`{"enabled":true,"channels":{"telegram":{"chat_id":"123"}}}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.UpdateSubscription(c)

		assert.Equal(t, http.StatusServiceUnavailable, w.Code)
	})

	t.Run("null channels coerced to empty map", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("PUT", "/api/v1/signals/subscription",
			strings.NewReader(`{"enabled":false}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.UpdateSubscription(c)

		// With nil db we expect 503, but parsing succeeds (no 400)
		assert.Equal(t, http.StatusServiceUnavailable, w.Code)
	})
}

func TestTestPush_Validation(t *testing.T) {
	gin.SetMode(gin.TestMode)

	notifMgr := notify.NewManager(nil)
	h := NewSignalPushHandler(nil, notifMgr)

	t.Run("unauthenticated returns 401", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("POST", "/api/v1/signals/subscription/test",
			strings.NewReader(`{"channel":"telegram"}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.TestPush(c)

		assert.Equal(t, http.StatusUnauthorized, w.Code)

		var resp map[string]string
		err := json.Unmarshal(w.Body.Bytes(), &resp)
		assert.NoError(t, err)
		assert.Equal(t, "authentication required", resp["error"])
	})

	t.Run("missing channel returns 400", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/signals/subscription/test",
			strings.NewReader(`{}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.TestPush(c)

		assert.Equal(t, http.StatusBadRequest, w.Code)
	})

	t.Run("valid request enqueues test push", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/signals/subscription/test",
			strings.NewReader(`{"channel":"telegram","config":{"chat_id":"123"}}`))
		c.Request.Header.Set("Content-Type", "application/json")

		h.TestPush(c)

		assert.Equal(t, http.StatusOK, w.Code)

		var resp map[string]interface{}
		err := json.Unmarshal(w.Body.Bytes(), &resp)
		assert.NoError(t, err)
		assert.Equal(t, "sent", resp["status"])
		assert.Equal(t, "telegram", resp["channel"])
	})

	t.Run("nil notification manager returns 503", func(t *testing.T) {
		hNoNotif := NewSignalPushHandler(nil, nil)

		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", 1)
		c.Request = httptest.NewRequest("POST", "/api/v1/signals/subscription/test",
			strings.NewReader(`{"channel":"telegram"}`))
		c.Request.Header.Set("Content-Type", "application/json")

		hNoNotif.TestPush(c)

		assert.Equal(t, http.StatusServiceUnavailable, w.Code)
	})
}

func TestPushSubscription_JSONMarshal(t *testing.T) {
	sub := PushSubscription{
		Enabled: true,
		Channels: map[string]json.RawMessage{
			"telegram": json.RawMessage(`{"chat_id":"123"}`),
			"email":    json.RawMessage(`{"to":"test@example.com"}`),
		},
	}

	data, err := json.Marshal(sub)
	assert.NoError(t, err)

	var decoded PushSubscription
	err = json.Unmarshal(data, &decoded)
	assert.NoError(t, err)
	assert.True(t, decoded.Enabled)
	assert.Len(t, decoded.Channels, 2)
	assert.JSONEq(t, `{"chat_id":"123"}`, string(decoded.Channels["telegram"]))
	assert.JSONEq(t, `{"to":"test@example.com"}`, string(decoded.Channels["email"]))
}

func TestPushSubscription_Defaults(t *testing.T) {
	sub := PushSubscription{}
	assert.False(t, sub.Enabled)
	assert.Nil(t, sub.Channels)

	data, err := json.Marshal(sub)
	assert.NoError(t, err)
	assert.JSONEq(t, `{"enabled":false,"channels":null}`, string(data))
}

func TestGetUserID_Helper(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := NewSignalPushHandler(nil, nil)

	t.Run("no user_id in context", func(t *testing.T) {
		c, _ := gin.CreateTestContext(httptest.NewRecorder())
		id, err := h.getUserID(c)
		assert.Equal(t, 0, id)
		assert.EqualError(t, err, "authentication required")
	})

	t.Run("user_id is not int", func(t *testing.T) {
		c, _ := gin.CreateTestContext(httptest.NewRecorder())
		c.Set("user_id", "not_an_int")
		id, err := h.getUserID(c)
		assert.Equal(t, 0, id)
		assert.EqualError(t, err, "invalid user id type")
	})

	t.Run("valid user_id", func(t *testing.T) {
		c, _ := gin.CreateTestContext(httptest.NewRecorder())
		c.Set("user_id", 42)
		id, err := h.getUserID(c)
		assert.NoError(t, err)
		assert.Equal(t, 42, id)
	})
}
