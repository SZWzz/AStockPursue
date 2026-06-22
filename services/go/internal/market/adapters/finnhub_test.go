package adapters

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/astockpursue/go-core/internal/market"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewFinnhubAdapter(t *testing.T) {
	adapter := NewFinnhubAdapter()
	assert.Equal(t, "finnhub", adapter.Name())
	assert.Equal(t, []string{"US"}, adapter.Markets())
}

func TestFinnhubRequiresAuth(t *testing.T) {
	t.Run("with api key set", func(t *testing.T) {
		os.Setenv("FINNHUB_API_KEY", "test-key")
		defer os.Unsetenv("FINNHUB_API_KEY")

		adapter := NewFinnhubAdapter()
		assert.True(t, adapter.RequiresAuth())
	})

	t.Run("without api key", func(t *testing.T) {
		os.Unsetenv("FINNHUB_API_KEY")

		adapter := &FinnhubAdapter{
			client: &http.Client{Timeout: 30 * time.Second},
		}
		assert.False(t, adapter.RequiresAuth())
	})
}

func TestFinnhubIsAvailable(t *testing.T) {
	t.Run("http 200 returns true", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
		}))
		defer server.Close()

		adapter := &FinnhubAdapter{
			client:  server.Client(),
			baseURL: server.URL,
			apiKey:  "test-key",
		}
		assert.True(t, adapter.IsAvailable(context.Background()))
	})

	t.Run("http 500 returns false", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusInternalServerError)
		}))
		defer server.Close()

		adapter := &FinnhubAdapter{
			client:  server.Client(),
			baseURL: server.URL,
			apiKey:  "test-key",
		}
		assert.False(t, adapter.IsAvailable(context.Background()))
	})

	t.Run("no api key returns false", func(t *testing.T) {
		adapter := &FinnhubAdapter{
			client: &http.Client{Timeout: 30 * time.Second},
		}
		assert.False(t, adapter.IsAvailable(context.Background()))
	})
}

func TestFinnhubFetchSuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"c": [150.0, 151.0, 152.0],
			"h": [152.0, 153.0, 154.0],
			"l": [148.0, 149.0, 150.0],
			"o": [149.0, 150.0, 151.0],
			"s": "ok",
			"t": [1688169600, 1688256000, 1688342400],
			"v": [1000000, 1100000, 1200000]
		}`))
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	bars, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "AAPL",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
		Frequency: "1d",
	})
	require.NoError(t, err)
	require.Len(t, bars, 3)

	assert.Equal(t, "AAPL", bars[0].Symbol)
	assert.Equal(t, 149.0, bars[0].Open)
	assert.Equal(t, 152.0, bars[0].High)
	assert.Equal(t, 148.0, bars[0].Low)
	assert.Equal(t, 150.0, bars[0].Close)
	assert.Equal(t, int64(1000000), bars[0].Volume)
	assert.Equal(t, int64(1688169600000), bars[0].Timestamp)
	assert.Equal(t, "1d", bars[0].Frequency)

	assert.Equal(t, 151.0, bars[1].Close)
	assert.Equal(t, 152.0, bars[2].Close)
}

func TestFinnhubFetchEmptyResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"s":"no_data"}`))
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	bars, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "INVALID",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
		Frequency: "1d",
	})
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "no_data")
	assert.Nil(t, bars)
}

func TestFinnhubFetchRateLimit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTooManyRequests)
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "AAPL",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
		Frequency: "1d",
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "rate limit")
}

func TestFinnhubFetchHTTPError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "AAPL",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
		Frequency: "1d",
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "HTTP 500")
}

func TestFinnhubFetchInsiderTransactions(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"data": [
				{
					"symbol": "AAPL",
					"shares": 10000,
					"change": -5000,
					"filingDate": "2023-07-01",
					"transactionDate": "2023-06-28",
					"transactionType": "Sell",
					"price": 150.5
				},
				{
					"symbol": "AAPL",
					"shares": 5000,
					"change": 5000,
					"filingDate": "2023-07-02",
					"transactionDate": "2023-06-30",
					"transactionType": "Buy",
					"price": 149.0
				}
			]
		}`))
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	transactions, err := adapter.FetchInsiderTransactions(
		context.Background(),
		"AAPL",
		time.Date(2023, 6, 1, 0, 0, 0, 0, time.UTC),
		time.Date(2023, 7, 31, 0, 0, 0, 0, time.UTC),
	)
	require.NoError(t, err)
	require.Len(t, transactions, 2)

	assert.Equal(t, "AAPL", transactions[0].Symbol)
	assert.Equal(t, int64(10000), transactions[0].Shares)
	assert.Equal(t, -5000.0, transactions[0].Change)
	assert.Equal(t, "2023-07-01", transactions[0].FilingDate)
	assert.Equal(t, "Sell", transactions[0].TransactionType)
	assert.Equal(t, 150.5, transactions[0].Price)

	assert.Equal(t, "Buy", transactions[1].TransactionType)
	assert.Equal(t, 149.0, transactions[1].Price)
}

func TestFinnhubFetchFilings(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"data": [
				{
					"symbol": "AAPL",
					"filingId": "0000320193-23-000070",
					"filingType": "10-K",
					"filedDate": "2023-10-26",
					"description": "Annual Report",
					"url": "https://sec.gov/Archives/edgar/data/320193/000032019323000070/aapl-20230930.htm"
				}
			]
		}`))
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	filings, err := adapter.FetchFilings(
		context.Background(),
		"AAPL",
		time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC),
		time.Date(2023, 12, 31, 0, 0, 0, 0, time.UTC),
	)
	require.NoError(t, err)
	require.Len(t, filings, 1)

	assert.Equal(t, "AAPL", filings[0].Symbol)
	assert.Equal(t, "0000320193-23-000070", filings[0].FilingID)
	assert.Equal(t, "10-K", filings[0].FilingType)
	assert.Equal(t, "2023-10-26", filings[0].FiledDate)
	assert.Equal(t, "Annual Report", filings[0].Description)
}

func TestFinnhubFetchNewsSentiment(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"symbol": "AAPL",
			"buzz": 0.75,
			"companyNewsScore": 0.65,
			"sectorAverageBullish": 0.55,
			"lastUpdated": "2023-07-15T12:00:00Z"
		}`))
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	sentiment, err := adapter.FetchNewsSentiment(context.Background(), "AAPL")
	require.NoError(t, err)
	require.NotNil(t, sentiment)

	assert.Equal(t, "AAPL", sentiment.Symbol)
	assert.Equal(t, 0.75, sentiment.Buzz)
	assert.Equal(t, 0.65, sentiment.CompanyNewsScore)
	assert.Equal(t, 0.55, sentiment.SectorAverageBullish)
	assert.Equal(t, "2023-07-15T12:00:00Z", sentiment.LastUpdated)
}

func TestFinnhubFetchNoAPIKey(t *testing.T) {
	adapter := &FinnhubAdapter{
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: "https://finnhub.io/api/v1",
	}

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "AAPL",
		StartDate: time.Now().AddDate(0, 0, -7),
		EndDate:   time.Now(),
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "FINNHUB_API_KEY not set")
}

func TestFinnhubFetchSkipsZeroOpenBars(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"c": [150.0, 0, 152.0],
			"h": [152.0, 0, 154.0],
			"l": [148.0, 0, 150.0],
			"o": [149.0, 0, 151.0],
			"s": "ok",
			"t": [1688169600, 1688256000, 1688342400],
			"v": [1000000, 0, 1200000]
		}`))
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	bars, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "AAPL",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
		Frequency: "1d",
	})
	require.NoError(t, err)
	// Should skip the bar with open=0
	assert.Len(t, bars, 2)
	assert.Equal(t, 150.0, bars[0].Close)
	assert.Equal(t, 152.0, bars[1].Close)
}

func TestFinnhubFetchEndDateDefaults(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"c": [150.0],
			"h": [152.0],
			"l": [148.0],
			"o": [149.0],
			"s": "ok",
			"t": [1688169600],
			"v": [1000000]
		}`))
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	bars, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "AAPL",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		Frequency: "1d",
	})
	require.NoError(t, err)
	assert.Len(t, bars, 1)
}

func TestFinnhubFetchMultipleResolutions(t *testing.T) {
	tests := []struct {
		freq       string
		expected   string
	}{
		{"1m", "1"},
		{"1", "1"},
		{"5", "5"},
		{"15", "15"},
		{"30", "30"},
		{"1h", "60"},
		{"60", "60"},
		{"W", "W"},
		{"1w", "W"},
		{"M", "M"},
		{"1M", "M"},
		{"1d", "D"},
		{"D", "D"},
		{"", "D"},
	}

	for _, tt := range tests {
		t.Run("frequency_"+tt.freq, func(t *testing.T) {
			adapter := &FinnhubAdapter{
				client:  &http.Client{Timeout: 30 * time.Second},
				baseURL: "http://localhost",
				apiKey:  "test-key",
			}
			result := adapter.resolveResolution(tt.freq)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestFinnhubFetchInsiderRateLimit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTooManyRequests)
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	_, err := adapter.FetchInsiderTransactions(
		context.Background(),
		"AAPL",
		time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC),
		time.Date(2023, 12, 31, 0, 0, 0, 0, time.UTC),
	)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "rate limit")
}

func TestFinnhubFetchFilingsRateLimit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTooManyRequests)
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	_, err := adapter.FetchFilings(
		context.Background(),
		"AAPL",
		time.Date(2023, 1, 1, 0, 0, 0, 0, time.UTC),
		time.Date(2023, 12, 31, 0, 0, 0, 0, time.UTC),
	)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "rate limit")
}

func TestFinnhubNewsSentimentRateLimit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTooManyRequests)
	}))
	defer server.Close()

	adapter := &FinnhubAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		apiKey:  "test-key",
	}

	_, err := adapter.FetchNewsSentiment(context.Background(), "AAPL")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "rate limit")
}

func TestStringOr(t *testing.T) {
	assert.Equal(t, "primary", stringOr("primary", "fallback"))
	assert.Equal(t, "fallback", stringOr("", "fallback"))
}
