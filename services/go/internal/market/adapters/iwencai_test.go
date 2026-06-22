package adapters

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/astockpursue/go-core/internal/market"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewIWenCaiAdapter(t *testing.T) {
	adapter := NewIWenCaiAdapter()
	assert.Equal(t, "iwencai", adapter.Name())
	assert.Equal(t, []string{"CN"}, adapter.Markets())
	assert.False(t, adapter.RequiresAuth())
}

func TestIWenCaiIsAvailable(t *testing.T) {
	adapter := NewIWenCaiAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusOK,
			Body:       io.NopCloser(nil),
			Header:     http.Header{"Content-Type": []string{"text/html"}},
		}, nil
	})

	assert.True(t, adapter.IsAvailable(context.Background()))
}

func TestIWenCaiIsAvailableNotAvailable(t *testing.T) {
	adapter := NewIWenCaiAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusInternalServerError,
			Body:       io.NopCloser(nil),
			Header:     http.Header{"Content-Type": []string{"text/html"}},
		}, nil
	})

	assert.False(t, adapter.IsAvailable(context.Background()))
}

func TestIWenCaiQuery(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// V1 format
		w.Write([]byte(`{
			"data": {
				"result": [
					{"code":"000001.SZ","name":"平安银行","score":"85.5","market":"3000"},
					{"code":"600000.SH","name":"浦发银行","score":"78.2","market":"2500"}
				],
				"totalCount": "2"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	stocks, err := adapter.Query(context.Background(), "银行股")
	require.NoError(t, err)
	require.Len(t, stocks, 2)

	assert.Equal(t, "000001", stocks[0].Code)
	assert.Equal(t, "平安银行", stocks[0].Name)
	assert.Equal(t, "SZ", stocks[0].Exchange)
	assert.Equal(t, 85.5, stocks[0].Score)
	assert.Equal(t, 3000.0, stocks[0].MarketCap)

	assert.Equal(t, "600000", stocks[1].Code)
	assert.Equal(t, "浦发银行", stocks[1].Name)
	assert.Equal(t, "SH", stocks[1].Exchange)
	assert.Equal(t, 78.2, stocks[1].Score)
}

func TestIWenCaiQueryV2Format(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"data": {
				"result": [
					{"stock_code":"000001.SZ","stock_name":"平安银行","relevance":"85.5","mc":"3000"}
				],
				"totalCount": "1"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	stocks, err := adapter.Query(context.Background(), "银行股")
	require.NoError(t, err)
	require.Len(t, stocks, 1)

	assert.Equal(t, "000001", stocks[0].Code)
	assert.Equal(t, "平安银行", stocks[0].Name)
	assert.Equal(t, "SZ", stocks[0].Exchange)
	assert.Equal(t, 85.5, stocks[0].Score)
	assert.Equal(t, 3000.0, stocks[0].MarketCap)
}

func TestIWenCaiQueryV3Format(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"data": {
				"result": [
					{"f1":"000001.SZ","f2":"平安银行","f3":"85.5","f20":"3000"}
				],
				"totalCount": "1"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	stocks, err := adapter.Query(context.Background(), "银行股")
	require.NoError(t, err)
	require.Len(t, stocks, 1)

	assert.Equal(t, "000001", stocks[0].Code)
	assert.Equal(t, "平安银行", stocks[0].Name)
	assert.Equal(t, "SZ", stocks[0].Exchange)
	assert.Equal(t, 85.5, stocks[0].Score)
	assert.Equal(t, 3000.0, stocks[0].MarketCap)
}

func TestIWenCaiQueryV3FormatShanghai(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"data": {
				"result": [
					{"f1":"600519.SH","f2":"贵州茅台","f3":"95.0","f20":"22000"}
				],
				"totalCount": "1"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	stocks, err := adapter.Query(context.Background(), "茅台")
	require.NoError(t, err)
	require.Len(t, stocks, 1)

	assert.Equal(t, "600519", stocks[0].Code)
	assert.Equal(t, "SH", stocks[0].Exchange)
}

func TestIWenCaiQueryJSONP(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/javascript")
		w.WriteHeader(http.StatusOK)
		// JSONP-wrapped response
		w.Write([]byte(`jsonp_12345({"data":{"result":[{"code":"000001.SZ","name":"平安银行","score":"85.5","market":"3000"}],"totalCount":"1"},"status":"ok"})`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	stocks, err := adapter.Query(context.Background(), "银行股")
	require.NoError(t, err)
	require.Len(t, stocks, 1)
	assert.Equal(t, "000001", stocks[0].Code)
}

func TestIWenCaiQueryHTTPError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	_, err := adapter.Query(context.Background(), "测试查询")
	require.Error(t, err)
}

func TestIWenCaiFetch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"data": {
				"result": [
					{"code":"000001.SZ","name":"平安银行","score":"85.5","market":"3000"},
					{"code":"600000.SH","name":"浦发银行","score":"78.2","market":"2500"}
				],
				"totalCount": "2"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	bars, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol: "银行股",
	})
	require.NoError(t, err)
	require.Len(t, bars, 2)

	// Score is used as Close (and all OHLC)
	assert.Equal(t, "000001", bars[0].Symbol)
	assert.Equal(t, 85.5, bars[0].Close)
	assert.Equal(t, 85.5, bars[0].Open)
	assert.Equal(t, 85.5, bars[0].High)
	assert.Equal(t, 85.5, bars[0].Low)
	// MarketCap (亿元) * 100 = volume
	assert.Equal(t, int64(300000), bars[0].Volume)
	assert.Equal(t, "1d", bars[0].Frequency)

	assert.Equal(t, "600000", bars[1].Symbol)
	assert.Equal(t, 78.2, bars[1].Close)
	assert.Equal(t, int64(250000), bars[1].Volume)
}

func TestIWenCaiFetchEmptyQuery(t *testing.T) {
	adapter := NewIWenCaiAdapter()

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol: "",
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "Symbol field must contain the query string")
}

func TestIWenCaiQueryEmpty(t *testing.T) {
	adapter := NewIWenCaiAdapter()

	_, err := adapter.Query(context.Background(), "")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "empty query")
}

func TestIWenCaiQueryEmptyResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"data": {
				"result": [],
				"totalCount": "0"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	_, err := adapter.Query(context.Background(), "不存在的条件")
	require.Error(t, err)
	// parseResponse handles empty result array; expect parse failure
	assert.Contains(t, err.Error(), "iwencai")
}

func TestSplitCode(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected struct{ code, exchange string }
	}{
		{
			name:     "SZ suffix",
			input:    "000001.SZ",
			expected: struct{ code, exchange string }{"000001", "SZ"},
		},
		{
			name:     "SH suffix",
			input:    "600519.SH",
			expected: struct{ code, exchange string }{"600519", "SH"},
		},
		{
			name:     "BJ suffix",
			input:    "430047.BJ",
			expected: struct{ code, exchange string }{"430047", "BJ"},
		},
		{
			name:     "SH prefix inference (6xxx)",
			input:    "600000",
			expected: struct{ code, exchange string }{"600000", "SH"},
		},
		{
			name:     "SZ prefix inference (0xxx)",
			input:    "000001",
			expected: struct{ code, exchange string }{"000001", "SZ"},
		},
		{
			name:     "SZ prefix inference (3xxx)",
			input:    "300750",
			expected: struct{ code, exchange string }{"300750", "SZ"},
		},
		{
			name:     "BJ prefix inference (4xxx)",
			input:    "430047",
			expected: struct{ code, exchange string }{"430047", "BJ"},
		},
		{
			name:     "BJ prefix inference (8xxx)",
			input:    "830799",
			expected: struct{ code, exchange string }{"830799", "BJ"},
		},
		{
			name:     "unknown prefix",
			input:    "999999",
			expected: struct{ code, exchange string }{"999999", ""},
		},
		{
			name:     "lowercase suffix",
			input:    "000001.sz",
			expected: struct{ code, exchange string }{"000001", "SZ"},
		},
		{
			name:     "trim whitespace",
			input:    " 000001.SZ ",
			expected: struct{ code, exchange string }{"000001", "SZ"},
		},
		{
			name:     "empty",
			input:    "",
			expected: struct{ code, exchange string }{"", ""},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			code, exchange := splitCode(tt.input)
			assert.Equal(t, tt.expected.code, code)
			assert.Equal(t, tt.expected.exchange, exchange)
		})
	}
}

func TestIWenCaiQueryNoResults(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// Zero results returned
		w.Write([]byte(`{
			"data": {
				"result": [],
				"totalCount": "0"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	_, err := adapter.Query(context.Background(), "测试空结果")
	require.Error(t, err)
}

func TestIWenCaiV2WithCodeInference(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"data": {
				"result": [
					{"stock_code":"000001","stock_name":"平安银行","relevance":"80","mc":"3000"}
				],
				"totalCount": "1"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	stocks, err := adapter.Query(context.Background(), "银行")
	require.NoError(t, err)
	require.Len(t, stocks, 1)
	assert.Equal(t, "000001", stocks[0].Code)
	assert.Equal(t, "SZ", stocks[0].Exchange, "should infer SZ from 0xxxx prefix")
}

func TestIWenCaiNoResultsReturnsError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// No results in V1 format
		w.Write([]byte(`{"data":{"result":[],"totalCount":"0"},"status":"ok"}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	_, err := adapter.Query(context.Background(), "测试")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "unable to parse")
}

func TestIWenCaiQueryItemsFormat(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// Response with "items" key inside result
		w.Write([]byte(`{
			"data": {
				"result": {
					"items": [
						{"code":"000001.SZ","name":"平安银行","score":"90","market":"3000"}
					]
				},
				"totalCount": "1"
			},
			"status": "ok"
		}`))
	}))
	defer server.Close()

	adapter := &IWenCaiAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	stocks, err := adapter.Query(context.Background(), "测试items格式")
	require.NoError(t, err)
	require.Len(t, stocks, 1)
	assert.Equal(t, "000001", stocks[0].Code)
}

func TestStripJSONP(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected string
	}{
		{
			name:     "standard jsonp",
			input:    `jsonp_12345({"data":{}})`,
			expected: `{"data":{}}`,
		},
		{
			name:     "no jsonp (plain json)",
			input:    `{"data":{}}`,
			expected: `{"data":{}}`,
		},
		{
			name:     "empty string",
			input:    "",
			expected: "",
		},
		{
			name:     "nested parentheses",
			input:    `foo({"key":"val(ue)"})`,
			expected: `{"key":"val(ue)"}`,
		},
		{
			name:     "array jsonp",
			input:    `callback([1,2,3])`,
			expected: `[1,2,3]`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := stripJSONP([]byte(tt.input))
			if tt.expected == "" {
				assert.Equal(t, tt.expected, string(result))
			} else {
				assert.JSONEq(t, tt.expected, string(result))
			}
		})
	}
}
