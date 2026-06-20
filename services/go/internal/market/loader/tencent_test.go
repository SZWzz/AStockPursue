package loader

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestTencentFetchBars(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`v_sz000001="0~平安银行~000001~10.0~10.5~11.0~9.5~1000000~5000000"`))
	}))
	defer server.Close()

	tl := &TencentLoader{client: http.DefaultClient, baseURL: server.URL}
	assert.Equal(t, "tencent", tl.Name())
	assert.True(t, tl.IsAvailable())

	bars, err := tl.FetchBars("000001", time.Time{}, time.Time{})
	assert.NoError(t, err)
	assert.Equal(t, 1, len(bars))
	assert.Equal(t, "000001", bars[0].Symbol)
	assert.Equal(t, 10.5, bars[0].Close)
}
