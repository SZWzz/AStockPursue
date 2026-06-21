package broker

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestBrokerFactoryRegistration(t *testing.T) {
	names := List()
	assert.Contains(t, names, "binance", "binance should be registered")
}

func TestBrokerFactoryCreateUnknown(t *testing.T) {
	_, err := New("unknown", BrokerConfig{})
	assert.Error(t, err)
}

func TestBinanceBrokerName(t *testing.T) {
	b, err := New("binance", BrokerConfig{APIKey: "test", Secret: "test", Testnet: true})
	assert.NoError(t, err)
	assert.Equal(t, "binance", b.Name())
}

func TestBinanceBrokerFeeRate(t *testing.T) {
	b, _ := New("binance", BrokerConfig{APIKey: "test", Secret: "test"})
	fee := b.GetFeeRate("BTCUSDT")
	assert.Equal(t, 0.0002, fee.Maker)
	assert.Equal(t, 0.0004, fee.Taker)
}

func TestBinanceBrokerGetPositions(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"totalWalletBalance":"10000.0","availableBalance":"8000.0","positions":[
			{"symbol":"BTCUSDT","positionAmt":"0.5","entryPrice":"40000.0","markPrice":"45000.0","unRealizedProfit":"2500.0"}
		]}`))
	}))
	defer server.Close()

	b := &BinanceBroker{apiKey: "k", secretKey: "s", baseURL: server.URL, client: http.DefaultClient}
	positions, err := b.GetPositions(context.Background())
	assert.NoError(t, err)
	assert.Equal(t, 1, len(positions))
	assert.Equal(t, "BTCUSDT", positions[0].Symbol)
	assert.Equal(t, 0.5, positions[0].Quantity)
	assert.Equal(t, 40000.0, positions[0].AvgPrice)
	assert.Equal(t, 45000.0, positions[0].CurrentPrice)
	assert.Equal(t, 2500.0, positions[0].UnrealizedPnL)
}

func TestBinanceBrokerGetBalance(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`[{"asset":"USDT","balance":"10000.0","availableBalance":"8000.0"},{"asset":"BTC","balance":"1.5","availableBalance":"0.5"}]`))
	}))
	defer server.Close()

	b := &BinanceBroker{apiKey: "k", secretKey: "s", baseURL: server.URL, client: http.DefaultClient}
	bal, err := b.GetBalance(context.Background())
	assert.NoError(t, err)
	assert.Equal(t, 10000.0, bal.Total)
	assert.Equal(t, 8000.0, bal.Available)
	assert.Equal(t, "USDT", bal.Currency)
}

func TestBinanceBrokerPlaceOrder(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodPost, r.Method)
		resp := binanceOrderResp{
			OrderID: 12345, Symbol: "BTCUSDT", Side: "BUY", Type: "MARKET",
			Price: "0", OrigQty: "0.1", ExecutedQty: "0.1", AvgPrice: "45000", Status: "FILLED",
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer server.Close()

	b := &BinanceBroker{apiKey: "k", secretKey: "s", baseURL: server.URL, client: http.DefaultClient}
	order, err := b.PlaceOrder(context.Background(), "BTCUSDT", Buy, Market, 0.1, 0)
	assert.NoError(t, err)
	assert.Equal(t, "12345", order.OrderID)
	assert.Equal(t, StatusFilled, order.Status)
	assert.Equal(t, 0.1, order.FilledQty)
}

func TestBinanceBrokerRequiresAPIKey(t *testing.T) {
	b := &BinanceBroker{apiKey: "", secretKey: "", baseURL: "http://localhost", client: http.DefaultClient}
	_, err := b.GetPositions(context.Background())
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "API key")
}

func TestDataTypeConstants(t *testing.T) {
	assert.Equal(t, OrderSide("buy"), Buy)
	assert.Equal(t, OrderSide("sell"), Sell)
	assert.Equal(t, OrderType("market"), Market)
	assert.Equal(t, OrderType("limit"), Limit)
	assert.Equal(t, OrderStatus("pending"), StatusPending)
	assert.Equal(t, OrderStatus("filled"), StatusFilled)
}

func TestOKXBrokerName(t *testing.T) {
	b, err := New("okx", BrokerConfig{APIKey: "k", Secret: "s", Passphrase: "p"})
	assert.NoError(t, err)
	assert.Equal(t, "okx", b.Name())
}

func TestOKXBrokerGetPositions(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"code":"0","data":[
			{"instId":"BTC-USDT-SWAP","pos":"0.5","avgPx":"40000","markPx":"45000","upl":"2500"},
			{"instId":"ETH-USDT-SWAP","pos":"0","avgPx":"0","markPx":"0","upl":"0"}
		]}`))
	}))
	defer server.Close()

	b := &OKXBroker{apiKey: "k", secretKey: "s", passphrase: "p", baseURL: server.URL, client: http.DefaultClient}
	positions, err := b.GetPositions(context.Background())
	assert.NoError(t, err)
	assert.Equal(t, 1, len(positions), "should filter out zero positions")
	assert.Equal(t, "BTC-USDT-SWAP", positions[0].Symbol)
}

func TestOKXBrokerGetBalance(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"code":"0","data":[{"details":[
			{"ccy":"USDT","eq":"10000","availEq":"8000","frozenBal":"2000"}
		]}]}`))
	}))
	defer server.Close()

	b := &OKXBroker{apiKey: "k", secretKey: "s", passphrase: "p", baseURL: server.URL, client: http.DefaultClient}
	bal, err := b.GetBalance(context.Background())
	assert.NoError(t, err)
	assert.Equal(t, 10000.0, bal.Total)
	assert.Equal(t, 8000.0, bal.Available)
	assert.Equal(t, 2000.0, bal.Frozen)
	assert.Equal(t, "USDT", bal.Currency)
}

func TestBrokerFactoryOKXRegistered(t *testing.T) {
	names := List()
	assert.Contains(t, names, "okx")
}
