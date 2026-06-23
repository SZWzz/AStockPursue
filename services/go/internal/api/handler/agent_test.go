package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func newTestAgentHandler() *AgentHandler {
	return NewAgentHandler()
}

func TestAgentChat_CreatesNewSession(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"我想创建一个策略"}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Chat(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	// Should return session_id and reply
	assert.NotEmpty(t, resp["session_id"])
	assert.NotEmpty(t, resp["reply"])
	assert.NotEmpty(t, resp["stage"])
}

func TestAgentChat_ReturnsSessionIDAndReply(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"趋势跟踪"}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Chat(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	assert.NotEmpty(t, resp["session_id"])
	reply, ok := resp["reply"].(string)
	assert.True(t, ok)
	assert.Contains(t, reply, "止损")
}

func TestAgentChat_RequiresAuth(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"hello"}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Chat(c)

	assert.Equal(t, http.StatusUnauthorized, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)
	assert.Equal(t, "authentication required", resp["error"])
}

func TestAgentChat_EmptyBodyReturns400(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 1)
	c.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{}`))
	c.Request.Header.Set("Content-Type", "application/json")

	h.Chat(c)

	assert.Equal(t, http.StatusBadRequest, w.Code)
}

func TestAgentChat_ExistingSessionAppendsMessages(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	// First chat creates a session
	w1 := httptest.NewRecorder()
	c1, _ := gin.CreateTestContext(w1)
	c1.Set("user_id", 1)
	c1.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"想创建趋势跟踪策略"}`))
	c1.Request.Header.Set("Content-Type", "application/json")

	h.Chat(c1)

	var resp1 map[string]interface{}
	json.Unmarshal(w1.Body.Bytes(), &resp1)
	sessionID := resp1["session_id"].(string)

	// Second chat uses same session_id
	w2 := httptest.NewRecorder()
	c2, _ := gin.CreateTestContext(w2)
	c2.Set("user_id", 1)
	c2.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"5%","session_id":"`+sessionID+`"}`))
	c2.Request.Header.Set("Content-Type", "application/json")

	h.Chat(c2)

	assert.Equal(t, http.StatusOK, w2.Code)

	var resp2 map[string]interface{}
	json.Unmarshal(w2.Body.Bytes(), &resp2)
	assert.Equal(t, sessionID, resp2["session_id"])

	// Verify messages were appended
	w3 := httptest.NewRecorder()
	c3, _ := gin.CreateTestContext(w3)
	c3.Params = gin.Params{{Key: "id", Value: sessionID}}
	c3.Request = httptest.NewRequest("GET", "/api/v1/agent/sessions/"+sessionID, nil)

	h.GetSession(c3)

	assert.Equal(t, http.StatusOK, w3.Code)

	var resp3 map[string]interface{}
	json.Unmarshal(w3.Body.Bytes(), &resp3)
	messages, ok := resp3["messages"].([]interface{})
	assert.True(t, ok)
	assert.Equal(t, 4, len(messages), "should have 4 messages (user+ai × 2)")
}

func TestAgentListSessions_EmptyListForNewUser(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("user_id", 999)
	c.Request = httptest.NewRequest("GET", "/api/v1/agent/sessions", nil)

	h.ListSessions(c)

	assert.Equal(t, http.StatusOK, w.Code)

	var resp map[string]interface{}
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	sessions, ok := resp["sessions"].([]interface{})
	assert.True(t, ok, "sessions should be an array")
	assert.Equal(t, 0, len(sessions), "new user should have no sessions")
}

func TestAgentListSessions_ReturnsCorrectMessageCount(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	// Create a session with messages for user 1
	w1 := httptest.NewRecorder()
	c1, _ := gin.CreateTestContext(w1)
	c1.Set("user_id", 1)
	c1.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"我想创建一个策略"}`))
	c1.Request.Header.Set("Content-Type", "application/json")
	h.Chat(c1)

	// Create another session for user 2
	w2 := httptest.NewRecorder()
	c2, _ := gin.CreateTestContext(w2)
	c2.Set("user_id", 2)
	c2.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"趋势跟踪"}`))
	c2.Request.Header.Set("Content-Type", "application/json")
	h.Chat(c2)

	// User 1 should only see their own sessions
	wList := httptest.NewRecorder()
	cList, _ := gin.CreateTestContext(wList)
	cList.Set("user_id", 1)
	cList.Request = httptest.NewRequest("GET", "/api/v1/agent/sessions", nil)

	h.ListSessions(cList)

	assert.Equal(t, http.StatusOK, wList.Code)

	var resp map[string]interface{}
	json.Unmarshal(wList.Body.Bytes(), &resp)
	sessions := resp["sessions"].([]interface{})
	assert.Equal(t, 1, len(sessions), "user 1 should see exactly 1 session")

	sess := sessions[0].(map[string]interface{})
	assert.Equal(t, float64(2), sess["message_count"], "each chat creates 2 messages (user + ai)")
}

func TestAgentGetSession_NotFound(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "id", Value: "nonexistent"}}
	c.Request = httptest.NewRequest("GET", "/api/v1/agent/sessions/nonexistent", nil)

	h.GetSession(c)

	assert.Equal(t, http.StatusNotFound, w.Code)

	var resp map[string]string
	err := json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)
	assert.Equal(t, "session not found", resp["error"])
}

func TestAgentDeleteSession_RemovesSession(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	// Create a session first
	w1 := httptest.NewRecorder()
	c1, _ := gin.CreateTestContext(w1)
	c1.Set("user_id", 1)
	c1.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"我想创建策略"}`))
	c1.Request.Header.Set("Content-Type", "application/json")
	h.Chat(c1)

	var resp1 map[string]interface{}
	json.Unmarshal(w1.Body.Bytes(), &resp1)
	sessionID := resp1["session_id"].(string)

	// Delete it
	wDel := httptest.NewRecorder()
	cDel, _ := gin.CreateTestContext(wDel)
	cDel.Params = gin.Params{{Key: "id", Value: sessionID}}
	cDel.Request = httptest.NewRequest("DELETE", "/api/v1/agent/sessions/"+sessionID, nil)

	h.DeleteSession(cDel)

	assert.Equal(t, http.StatusOK, wDel.Code)

	var delResp map[string]interface{}
	json.Unmarshal(wDel.Body.Bytes(), &delResp)
	assert.Equal(t, true, delResp["deleted"])

	// Verify it's gone
	wGet := httptest.NewRecorder()
	cGet, _ := gin.CreateTestContext(wGet)
	cGet.Params = gin.Params{{Key: "id", Value: sessionID}}
	cGet.Request = httptest.NewRequest("GET", "/api/v1/agent/sessions/"+sessionID, nil)

	h.GetSession(cGet)

	assert.Equal(t, http.StatusNotFound, wGet.Code)
}

func TestAgentChat_DifferentUsersIsolated(t *testing.T) {
	gin.SetMode(gin.TestMode)
	h := newTestAgentHandler()

	// User 1 creates a session
	w1 := httptest.NewRecorder()
	c1, _ := gin.CreateTestContext(w1)
	c1.Set("user_id", 1)
	c1.Request = httptest.NewRequest("POST", "/api/v1/agent/chat",
		strings.NewReader(`{"message":"我想创建策略"}`))
	c1.Request.Header.Set("Content-Type", "application/json")
	h.Chat(c1)

	// User 2 lists sessions — should be empty
	w2 := httptest.NewRecorder()
	c2, _ := gin.CreateTestContext(w2)
	c2.Set("user_id", 2)
	c2.Request = httptest.NewRequest("GET", "/api/v1/agent/sessions", nil)

	h.ListSessions(c2)

	assert.Equal(t, http.StatusOK, w2.Code)

	var resp map[string]interface{}
	json.Unmarshal(w2.Body.Bytes(), &resp)
	sessions := resp["sessions"].([]interface{})
	assert.Equal(t, 0, len(sessions), "user 2 should not see user 1's sessions")
}

func TestGenerateAIReply_StyleDetection(t *testing.T) {
	tests := []struct {
		name     string
		message  string
		contains string
	}{
		{"trend style", "我想用趋势跟踪", "止损"},
		{"mean reversion", "用均值回归吧", "止损"},
		{"momentum", "动量策略", "止损"},
		{"stop loss question", "止损设置为5%", "持仓"},
		{"position count", "持仓3只股票", "交易频率"},
		{"frequency daily", "每日", "确认"},
		{"frequency hourly", "hourly", "确认"},
		{"frequency weekly", "weekly", "确认"},
		{"adjust", "调整参数", "调整哪些参数"},
		{"confirmation yes", "yes", "策略摘要"},
		{"confirmation ok", "ok", "策略摘要"},
		{"confirmation 好", "好", "策略摘要"},
		{"default", "随便聊点什么", "策略"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			history := []ChatMessage{
				{Role: "user", Content: "我想创建策略"},
				{Role: "assistant", Content: "请选择策略风格"},
			}
			reply := generateAIReply(tt.message, history)
			assert.Contains(t, reply, tt.contains)
		})
	}
}

func TestGenerateAIReply_StrategySummary(t *testing.T) {
	history := []ChatMessage{
		{Role: "user", Content: "趋势跟踪"},
		{Role: "assistant", Content: "请告诉我止损比例"},
		{Role: "user", Content: "5%止损"},
		{Role: "assistant", Content: "请告诉我持仓数量"},
	}
	reply := generateAIReply("好的", history)
	assert.Contains(t, reply, "策略摘要")
	assert.Contains(t, reply, "趋势跟踪")
	assert.Contains(t, reply, "5%")
}

func TestDetectStage(t *testing.T) {
	tests := []struct {
		reply string
		stage string
	}{
		{"策略摘要已生成", "summary"},
		{"请设置止损比例", "stop_loss"},
		{"请告诉我持仓数量", "positions"},
		{"选择交易频率", "frequency"},
		{"你想调整哪些参数", "adjust"},
		{"选择策略风格", "style"},
		{"你好，我能帮你什么", "greeting"},
	}

	for _, tt := range tests {
		t.Run(tt.stage, func(t *testing.T) {
			assert.Equal(t, tt.stage, detectStage(tt.reply))
		})
	}
}
