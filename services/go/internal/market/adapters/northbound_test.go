package adapters

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	commonv1 "github.com/astockpursue/go-core/internal/gen/common/v1"
	"github.com/astockpursue/go-core/internal/market"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewNorthboundAdapter(t *testing.T) {
	adapter := NewNorthboundAdapter()
	assert.Equal(t, "northbound", adapter.Name())
	assert.Equal(t, []string{"CN"}, adapter.Markets())
	assert.False(t, adapter.RequiresAuth())
}

func TestNorthboundIsAvailable(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	adapter := &NorthboundAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}
	assert.True(t, adapter.IsAvailable(context.Background()))
}

func TestNorthboundIsAvailableNotAvailable(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	adapter := &NorthboundAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}
	assert.False(t, adapter.IsAvailable(context.Background()))
}

func TestNorthboundFetch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// Kline format: date,sh_net_inflow,sz_net_inflow,total_net_inflow,cumulative
		w.Write([]byte(`{
			"data": {
				"klines": [
					"2023-07-01,5000,-2000,3000,50000",
					"2023-07-02,-1000,4000,3000,53000",
					"2023-07-03,2000,1000,3000,56000"
				]
			}
		}`))
	}))
	defer server.Close()

	adapter := &NorthboundAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	bars, err := adapter.Fetch(context.Background(), market.FetchRequest{
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	})
	require.NoError(t, err)
	require.Len(t, bars, 3)

	// First bar: sh=5000, sz=-2000, total=3000, cumulative=50000
	assert.Equal(t, "northbound", bars[0].Symbol)
	assert.Equal(t, 3000.0, bars[0].Close)
	assert.Equal(t, 5000.0, bars[0].High, "high = max(sh, sz) = 5000")
	assert.Equal(t, -2000.0, bars[0].Low, "low = min(sh, sz) = -2000")
	assert.Equal(t, int64(50000), bars[0].Volume)
	assert.Equal(t, "1d", bars[0].Frequency)

	// After sorting and backfill, first bar Open = Close
	assert.Equal(t, bars[0].Close, bars[0].Open)

	// Second bar: sh=-1000, sz=4000, total=3000
	assert.Equal(t, 3000.0, bars[1].Close)
	assert.Equal(t, 4000.0, bars[1].High)
	assert.Equal(t, -1000.0, bars[1].Low)
	// Second bar's Open should be backfilled from first bar's Close
	assert.Equal(t, bars[0].Close, bars[1].Open)
}

func TestNorthboundFetchEmpty(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"data":{"klines":[]}}`))
	}))
	defer server.Close()

	adapter := &NorthboundAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "no data")
}

func TestNorthboundFetchHTTPError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	adapter := &NorthboundAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "HTTP 500")
}

func TestNorthboundFetchTop10Active(t *testing.T) {
	adapter := NewNorthboundAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		body := `{
			"data": {
				"diff": [
					{"f12":"600519","f14":"贵州茅台","f4":"1680.5","f60":"50000","f61":"30000","f62":"20000","f63":"2.5"},
					{"f12":"000858","f14":"五粮液","f4":"168.0","f60":"30000","f61":"20000","f62":"10000","f63":"1.8"}
				]
			}
		}`
		return &http.Response{
			StatusCode: http.StatusOK,
			Body:       io.NopCloser(strings.NewReader(body)),
			Header:     http.Header{"Content-Type": []string{"application/json"}},
		}, nil
	})

	stocks, err := adapter.FetchTop10Active(context.Background())
	require.NoError(t, err)
	require.Len(t, stocks, 2)

	assert.Equal(t, "600519", stocks[0].Code)
	assert.Equal(t, "贵州茅台", stocks[0].Name)
	assert.Equal(t, 1680.5, stocks[0].Price)
	assert.Equal(t, 20000.0, stocks[0].NetInflow)
	assert.Equal(t, 50000.0, stocks[0].BuyAmount)
	assert.Equal(t, 30000.0, stocks[0].SellAmount)
	assert.Equal(t, 2.5, stocks[0].InflowPercent)
	assert.Equal(t, 1, stocks[0].Rank)

	assert.Equal(t, "000858", stocks[1].Code)
	assert.Equal(t, 2, stocks[1].Rank)
}

func TestNorthboundFetchTop10Empty(t *testing.T) {
	adapter := NewNorthboundAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusOK,
			Body:       io.NopCloser(strings.NewReader(`{"data":{"diff":[]}}`)),
			Header:     http.Header{"Content-Type": []string{"application/json"}},
		}, nil
	})

	_, err := adapter.FetchTop10Active(context.Background())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "no data")
}

func TestNorthboundFetchSectorDistribution(t *testing.T) {
	adapter := NewNorthboundAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		body := `{
			"data": {
				"diff": [
					{"f14":"白酒","f4":"50000","f5":"18"},
					{"f14":"新能源","f4":"30000","f5":"25"}
				]
			}
		}`
		return &http.Response{
			StatusCode: http.StatusOK,
			Body:       io.NopCloser(strings.NewReader(body)),
			Header:     http.Header{"Content-Type": []string{"application/json"}},
		}, nil
	})

	sectors, err := adapter.FetchSectorDistribution(context.Background())
	require.NoError(t, err)
	require.Len(t, sectors, 2)

	assert.Equal(t, "白酒", sectors[0].SectorName)
	assert.Equal(t, 50000.0, sectors[0].NetInflow)
	assert.Equal(t, 18, sectors[0].StockCount)
	assert.Equal(t, 1, sectors[0].Rank)

	assert.Equal(t, "新能源", sectors[1].SectorName)
	assert.Equal(t, 2, sectors[1].Rank)
}

func TestNorthboundFetchSectorEmpty(t *testing.T) {
	adapter := NewNorthboundAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusOK,
			Body:       io.NopCloser(strings.NewReader(`{"data":{"diff":[]}}`)),
			Header:     http.Header{"Content-Type": []string{"application/json"}},
		}, nil
	})

	_, err := adapter.FetchSectorDistribution(context.Background())
	require.Error(t, err)
	assert.Contains(t, err.Error(), "no data")
}

func TestParseKline(t *testing.T) {
	adapter := NewNorthboundAdapter()

	tests := []struct {
		name      string
		input     string
		expectErr bool
		check     func(*testing.T, *commonv1.Bar)
	}{
		{
			name:  "valid 5-field kline",
			input: "2023-07-01,5000,-2000,3000,50000",
			check: func(t *testing.T, bar *commonv1.Bar) {
				assert.Equal(t, 3000.0, bar.Close)
				assert.Equal(t, 5000.0, bar.High)
				assert.Equal(t, -2000.0, bar.Low)
				assert.Equal(t, int64(50000), bar.Volume)
				assert.Equal(t, "northbound", bar.Symbol)
				assert.Equal(t, "1d", bar.Frequency)
			},
		},
		{
			name:  "valid 4-field kline (no cumulative)",
			input: "2023-07-01,5000,-2000,3000",
			check: func(t *testing.T, bar *commonv1.Bar) {
				assert.Equal(t, 3000.0, bar.Close)
				assert.Equal(t, int64(0), bar.Volume, "cumulative defaults to 0")
			},
		},
		{
			name:      "malformed fewer than 4 fields",
			input:     "2023-07-01,5000,-2000",
			expectErr: true,
		},
		{
			name:      "invalid date",
			input:     "not-a-date,5000,-2000,3000,50000",
			expectErr: true,
		},
		{
			name:  "all zero flow values",
			input: "2023-07-01,0,0,0,50000",
			check: func(t *testing.T, bar *commonv1.Bar) {
				assert.Equal(t, 0.0, bar.Close)
				assert.Equal(t, 0.0, bar.High)
				assert.Equal(t, 0.0, bar.Low)
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			bar, err := adapter.parseKline(tt.input)
			if tt.expectErr {
				assert.Error(t, err)
				return
			}
			require.NoError(t, err)
			require.NotNil(t, bar)
			if tt.check != nil {
				tt.check(t, bar)
			}
		})
	}
}

func TestDaysInRange(t *testing.T) {
	tests := []struct {
		name     string
		start    time.Time
		end      time.Time
		expected int
	}{
		{
			name:     "3 day range",
			start:    time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
			end:      time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
			expected: 3,
		},
		{
			name:     "same day",
			start:    time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
			end:      time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
			expected: 1,
		},
		{
			name:     "one year range",
			start:    time.Date(2022, 7, 1, 0, 0, 0, 0, time.UTC),
			end:      time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
			expected: 366,
		},
		{
			name:     "end before start",
			start:    time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
			end:      time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
			expected: 1,
		},
		{
			name:     "zero time",
			start:    time.Time{},
			end:      time.Time{},
			expected: 1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := daysInRange(tt.start, tt.end)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestNorthboundFetchSortsAndBackfills(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		// Unsorted data
		w.Write([]byte(`{
			"data": {
				"klines": [
					"2023-07-03,2000,1000,3000,56000",
					"2023-07-01,5000,-2000,3000,50000",
					"2023-07-02,-1000,4000,3000,53000"
				]
			}
		}`))
	}))
	defer server.Close()

	adapter := &NorthboundAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	bars, err := adapter.Fetch(context.Background(), market.FetchRequest{
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	})
	require.NoError(t, err)
	require.Len(t, bars, 3)

	// Should be sorted by timestamp
	assert.True(t, bars[0].Timestamp < bars[1].Timestamp)
	assert.True(t, bars[1].Timestamp < bars[2].Timestamp)

	// First bar: Open = Close (no previous bar)
	assert.Equal(t, bars[0].Close, bars[0].Open)
	// Subsequent bars: Open = previous bar's Close
	assert.Equal(t, bars[0].Close, bars[1].Open)
	assert.Equal(t, bars[1].Close, bars[2].Open)
}

func TestNorthboundFetchTop10HTTPError(t *testing.T) {
	adapter := NewNorthboundAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusInternalServerError,
			Body:       io.NopCloser(strings.NewReader("")),
			Header:     http.Header{"Content-Type": []string{"application/json"}},
		}, nil
	})

	_, err := adapter.FetchTop10Active(context.Background())
	require.Error(t, err)
}

func TestNorthboundFetchSectorHTTPError(t *testing.T) {
	adapter := NewNorthboundAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusInternalServerError,
			Body:       io.NopCloser(strings.NewReader("")),
			Header:     http.Header{"Content-Type": []string{"application/json"}},
		}, nil
	})

	_, err := adapter.FetchSectorDistribution(context.Background())
	require.Error(t, err)
}

func TestNorthboundFetchNoData(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"data":null}`))
	}))
	defer server.Close()

	adapter := &NorthboundAdapter{
		client:  server.Client(),
		baseURL: server.URL,
	}

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	})
	require.Error(t, err)
}
