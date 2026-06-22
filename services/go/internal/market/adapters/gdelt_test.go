package adapters

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/astockpursue/go-core/internal/market"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// roundTripperFunc adapts a function to http.RoundTripper.
type roundTripperFunc func(*http.Request) (*http.Response, error)

func (f roundTripperFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func TestNewGDELTAdapter(t *testing.T) {
	adapter := NewGDELTAdapter()
	assert.Equal(t, "gdelt", adapter.Name())
	assert.Equal(t, []string{"GEOPOLITICAL"}, adapter.Markets())
	assert.False(t, adapter.RequiresAuth())
	assert.Len(t, adapter.Topics(), 10)
}

func TestGDELTIsAvailable(t *testing.T) {
	adapter := NewGDELTAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		assert.Equal(t, http.MethodHead, req.Method)
		return &http.Response{
			StatusCode: http.StatusOK,
			Body:       io.NopCloser(strings.NewReader("")),
			Header:     http.Header{"Content-Type": []string{"application/json"}},
		}, nil
	})

	assert.True(t, adapter.IsAvailable(context.Background()))
}

func TestGDELTIsAvailableNotAvailable(t *testing.T) {
	adapter := NewGDELTAdapter()
	adapter.client.Transport = roundTripperFunc(func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusInternalServerError,
			Body:       io.NopCloser(strings.NewReader("")),
			Header:     http.Header{"Content-Type": []string{"application/json"}},
		}, nil
	})

	assert.False(t, adapter.IsAvailable(context.Background()))
}

func TestGDELTFetch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)

		mode := r.URL.Query().Get("mode")
		if mode == "TimelineVol" {
			w.Write([]byte(`{"timeline":[{"date":"2023-07-01","value":500},{"date":"2023-07-02","value":600}]}`))
		} else {
			w.Write([]byte(`{"timeline":[{"date":"2023-07-01","value":3.5},{"date":"2023-07-02","value":-2.0}]}`))
		}
	}))
	defer server.Close()

	adapter := &GDELTAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		topics:  defaultTopics(),
	}

	bars, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "us-china-trade",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
		Frequency: "1d",
	})
	require.NoError(t, err)
	require.Len(t, bars, 2)

	// First bar: tone=3.5, volume=500
	assert.Equal(t, "us-china-trade", bars[0].Symbol)
	assert.Equal(t, 3.5, bars[0].Close)
	assert.Equal(t, int64(500), bars[0].Volume)
	assert.Equal(t, "1d", bars[0].Frequency)

	// Second bar: tone=-2.0, volume=600
	assert.Equal(t, -2.0, bars[1].Close)
	assert.Equal(t, int64(600), bars[1].Volume)

	// Verify bars are sorted by timestamp
	assert.True(t, bars[0].Timestamp <= bars[1].Timestamp)
}

func TestGDELTFetchUnknownTopic(t *testing.T) {
	adapter := NewGDELTAdapter()

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "nonexistent-topic",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "unknown topic")
}

func TestGDELTFetchTopicVolume(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"timeline":[
			{"date":"2023-07-01","value":100},
			{"date":"2023-07-02","value":200},
			{"date":"2023-07-03","value":150}
		]}`))
	}))
	defer server.Close()

	adapter := &GDELTAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		topics:  defaultTopics(),
	}

	points, err := adapter.FetchTopicVolume(
		context.Background(),
		"us-china-trade",
		time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	)
	require.NoError(t, err)
	require.Len(t, points, 3)

	assert.Equal(t, int64(100), points[0].Volume)
	assert.Equal(t, int64(200), points[1].Volume)
	assert.Equal(t, int64(150), points[2].Volume)

	assert.Equal(t, 2023, points[0].Date.Year())
	assert.Equal(t, time.July, points[0].Date.Month())
	assert.Equal(t, 1, points[0].Date.Day())
}

func TestGDELTFetchTopicVolumeUnknownTopic(t *testing.T) {
	adapter := NewGDELTAdapter()

	_, err := adapter.FetchTopicVolume(
		context.Background(),
		"nonexistent",
		time.Now().AddDate(0, 0, -7),
		time.Now(),
	)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "unknown topic")
}

func TestGDELTFetchTopicTone(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"timeline":[
			{"date":"2023-07-01","value":5.0},
			{"date":"2023-07-02","value":-3.5},
			{"date":"2023-07-03","value":2.1}
		]}`))
	}))
	defer server.Close()

	adapter := &GDELTAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		topics:  defaultTopics(),
	}

	points, err := adapter.FetchTopicTone(
		context.Background(),
		"russia-ukraine",
		time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	)
	require.NoError(t, err)
	require.Len(t, points, 3)

	assert.Equal(t, 5.0, points[0].Tone)
	assert.Equal(t, -3.5, points[1].Tone)
	assert.Equal(t, 2.1, points[2].Tone)
}

func TestGDELTFetchTopicToneUnknownTopic(t *testing.T) {
	adapter := NewGDELTAdapter()

	_, err := adapter.FetchTopicTone(
		context.Background(),
		"nonexistent",
		time.Now().AddDate(0, 0, -7),
		time.Now(),
	)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "unknown topic")
}

func TestGDELTTopics(t *testing.T) {
	adapter := NewGDELTAdapter()

	topics := adapter.Topics()
	require.Len(t, topics, 10)

	// Verify topics returns a copy, not a reference.
	topics[0].Name = "modified"
	originalTopics := adapter.Topics()
	assert.Equal(t, "us-china-trade", originalTopics[0].Name, "modifying returned slice should not affect original")
}

func TestGDELTConcurrentFetch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)

		mode := r.URL.Query().Get("mode")
		if mode == "TimelineVol" {
			w.Write([]byte(`{"timeline":[{"date":"2023-07-01","value":100}]}`))
		} else {
			w.Write([]byte(`{"timeline":[{"date":"2023-07-01","value":2.5}]}`))
		}
	}))
	defer server.Close()

	adapter := &GDELTAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		topics:  defaultTopics(),
	}

	var wg sync.WaitGroup
	errCh := make(chan error, 10)

	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := adapter.Fetch(context.Background(), market.FetchRequest{
				Symbol:    "us-china-trade",
				StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
				EndDate:   time.Date(2023, 7, 2, 0, 0, 0, 0, time.UTC),
			})
			if err != nil {
				errCh <- err
			}
		}()
	}

	wg.Wait()
	close(errCh)

	for err := range errCh {
		t.Errorf("unexpected error in concurrent fetch: %v", err)
	}
}

func TestGDELTFetchHTTPError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	adapter := &GDELTAdapter{
		client:  server.Client(),
		baseURL: server.URL,
		topics:  defaultTopics(),
	}

	_, err := adapter.Fetch(context.Background(), market.FetchRequest{
		Symbol:    "us-china-trade",
		StartDate: time.Date(2023, 7, 1, 0, 0, 0, 0, time.UTC),
		EndDate:   time.Date(2023, 7, 3, 0, 0, 0, 0, time.UTC),
	})
	require.Error(t, err)
}

func TestGDELTCustomTopicQuery(t *testing.T) {
	adapter := &GDELTAdapter{
		client:  &http.Client{Timeout: 30 * time.Second},
		baseURL: "https://api.gdeltproject.org/api/v2/doc/doc",
		topics: []TopicQuery{
			{Name: "custom-topic", Keyword: "custom query", Description: "Test"},
		},
	}

	assert.Len(t, adapter.Topics(), 1)
	assert.Equal(t, "custom-topic", adapter.Topics()[0].Name)
}
