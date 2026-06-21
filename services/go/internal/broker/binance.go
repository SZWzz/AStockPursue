package broker

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

func init() {
	Register("binance", NewBinanceBroker)
}

// BinanceBroker implements Broker for Binance USDT-M Futures.
// Uses the Binance REST API directly with HMAC-SHA256 signing.
type BinanceBroker struct {
	apiKey    string
	secretKey string
	baseURL   string
	client    *http.Client
}

type binanceOrderResp struct {
	OrderID      int64  `json:"orderId"`
	Symbol       string `json:"symbol"`
	Side         string `json:"side"`
	Type         string `json:"type"`
	Price        string `json:"price"`
	OrigQty      string `json:"origQty"`
	ExecutedQty  string `json:"executedQty"`
	AvgPrice     string `json:"avgPrice"`
	Status       string `json:"status"`
	RejectReason string `json:"rejectReason,omitempty"`
}

type binanceAccountResp struct {
	AvailableBalance string `json:"availableBalance"`
	TotalWalletBalance string `json:"totalWalletBalance"`
	Positions []binancePositionResp `json:"positions"`
}

type binancePositionResp struct {
	Symbol           string `json:"symbol"`
	PositionAmt      string `json:"positionAmt"`
	EntryPrice       string `json:"entryPrice"`
	MarkPrice        string `json:"markPrice"`
	UnrealizedProfit string `json:"unRealizedProfit"`
}

// NewBinanceBroker creates a new Binance Futures broker.
func NewBinanceBroker(cfg BrokerConfig) (Broker, error) {
	baseURL := "https://fapi.binance.com"
	if cfg.Testnet {
		baseURL = "https://testnet.binancefuture.com"
	}
	return &BinanceBroker{
		apiKey:    cfg.APIKey,
		secretKey: cfg.Secret,
		baseURL:   baseURL,
		client:    &http.Client{Timeout: 30 * time.Second},
	}, nil
}

func (b *BinanceBroker) Name() string { return "binance" }

func (b *BinanceBroker) TestConnection(ctx context.Context) error {
	_, err := b.signedGet(ctx, "/fapi/v2/balance", nil)
	return err
}

func (b *BinanceBroker) GetFeeRate(symbol string) FeeRate {
	return FeeRate{Maker: 0.0002, Taker: 0.0004}
}

// ── Order management ──────────────────────────────────────────────

func (b *BinanceBroker) PlaceOrder(ctx context.Context, symbol string, side OrderSide, orderType OrderType, quantity, price float64) (*Order, error) {
	params := url.Values{}
	params.Set("symbol", strings.ToUpper(symbol))
	params.Set("side", strings.ToUpper(string(side)))
	params.Set("type", strings.ToUpper(string(orderType)))
	params.Set("quantity", strconv.FormatFloat(quantity, 'f', -1, 64))
	if orderType == Limit && price > 0 {
		params.Set("price", strconv.FormatFloat(price, 'f', -1, 64))
		params.Set("timeInForce", "GTC")
	}

	body, err := b.signedPost(ctx, "/fapi/v1/order", params)
	if err != nil {
		return nil, err
	}

	var resp binanceOrderResp
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("binance parse order: %w", err)
	}
	return b.toOrder(&resp), nil
}

func (b *BinanceBroker) CancelOrder(ctx context.Context, orderID, symbol string) error {
	params := url.Values{}
	params.Set("symbol", strings.ToUpper(symbol))
	params.Set("orderId", orderID)
	_, err := b.signedDelete(ctx, "/fapi/v1/order", params)
	return err
}

func (b *BinanceBroker) GetOrder(ctx context.Context, orderID, symbol string) (*Order, error) {
	params := url.Values{}
	params.Set("symbol", strings.ToUpper(symbol))
	params.Set("orderId", orderID)
	body, err := b.signedGet(ctx, "/fapi/v1/order", params)
	if err != nil {
		return nil, err
	}
	var resp binanceOrderResp
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("binance parse order: %w", err)
	}
	return b.toOrder(&resp), nil
}

func (b *BinanceBroker) GetOpenOrders(ctx context.Context, symbol string) ([]*Order, error) {
	params := url.Values{}
	if symbol != "" {
		params.Set("symbol", strings.ToUpper(symbol))
	}
	body, err := b.signedGet(ctx, "/fapi/v1/openOrders", params)
	if err != nil {
		return nil, err
	}
	var responses []binanceOrderResp
	if err := json.Unmarshal(body, &responses); err != nil {
		return nil, fmt.Errorf("binance parse open orders: %w", err)
	}
	orders := make([]*Order, len(responses))
	for i := range responses {
		orders[i] = b.toOrder(&responses[i])
	}
	return orders, nil
}

// ── Position & balance ────────────────────────────────────────────

func (b *BinanceBroker) GetPosition(ctx context.Context, symbol string) (*Position, error) {
	positions, err := b.GetPositions(ctx)
	if err != nil {
		return nil, err
	}
	sym := strings.ToUpper(symbol)
	for _, p := range positions {
		if strings.EqualFold(p.Symbol, sym) {
			return p, nil
		}
	}
	return &Position{Symbol: sym}, nil
}

func (b *BinanceBroker) GetPositions(ctx context.Context) ([]*Position, error) {
	body, err := b.signedGet(ctx, "/fapi/v2/account", nil)
	if err != nil {
		return nil, err
	}
	var resp binanceAccountResp
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("binance parse account: %w", err)
	}
	var positions []*Position
	for _, bp := range resp.Positions {
		qty, _ := strconv.ParseFloat(bp.PositionAmt, 64)
		if qty == 0 {
			continue
		}
		avgPrice, _ := strconv.ParseFloat(bp.EntryPrice, 64)
		markPrice, _ := strconv.ParseFloat(bp.MarkPrice, 64)
		upnl, _ := strconv.ParseFloat(bp.UnrealizedProfit, 64)
		positions = append(positions, &Position{
			Symbol:        bp.Symbol,
			Quantity:      qty,
			AvgPrice:      avgPrice,
			CurrentPrice:  markPrice,
			UnrealizedPnL: upnl,
		})
	}
	return positions, nil
}

func (b *BinanceBroker) GetBalance(ctx context.Context) (*Balance, error) {
	body, err := b.signedGet(ctx, "/fapi/v2/balance", nil)
	if err != nil {
		return nil, err
	}
	var results []struct {
		Asset              string `json:"asset"`
		Balance            string `json:"balance"`
		AvailableBalance   string `json:"availableBalance"`
	}
	if err := json.Unmarshal(body, &results); err != nil {
		return nil, fmt.Errorf("binance parse balance: %w", err)
	}
	for _, r := range results {
		if r.Asset == "USDT" {
			total, _ := strconv.ParseFloat(r.Balance, 64)
			avail, _ := strconv.ParseFloat(r.AvailableBalance, 64)
			return &Balance{
				Total:     total,
				Available: avail,
				Frozen:    total - avail,
				Currency:  "USDT",
			}, nil
		}
	}
	return &Balance{Currency: "USDT"}, nil
}

// ── Private helpers ───────────────────────────────────────────────

func (b *BinanceBroker) sign(params url.Values) url.Values {
	if params == nil {
		params = url.Values{}
	}
	params.Set("timestamp", strconv.FormatInt(time.Now().UnixMilli(), 10))
	mac := hmac.New(sha256.New, []byte(b.secretKey))
	_, _ = mac.Write([]byte(params.Encode()))
	params.Set("signature", hex.EncodeToString(mac.Sum(nil)))
	return params
}

func (b *BinanceBroker) signedGet(ctx context.Context, path string, params url.Values) ([]byte, error) {
	return b.signedRequest(ctx, http.MethodGet, path, params)
}

func (b *BinanceBroker) signedPost(ctx context.Context, path string, params url.Values) ([]byte, error) {
	return b.signedRequest(ctx, http.MethodPost, path, params)
}

func (b *BinanceBroker) signedDelete(ctx context.Context, path string, params url.Values) ([]byte, error) {
	return b.signedRequest(ctx, http.MethodDelete, path, params)
}

func (b *BinanceBroker) signedRequest(ctx context.Context, method, path string, params url.Values) ([]byte, error) {
	if b.apiKey == "" || b.secretKey == "" {
		return nil, fmt.Errorf("binance: API key and secret required")
	}
	params = b.sign(params)

	var body io.Reader
	urlStr := b.baseURL + path
	if method == http.MethodGet || method == http.MethodDelete {
		urlStr += "?" + params.Encode()
	} else {
		body = strings.NewReader(params.Encode())
	}

	req, err := http.NewRequestWithContext(ctx, method, urlStr, body)
	if err != nil {
		return nil, fmt.Errorf("binance request: %w", err)
	}
	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	if method == http.MethodPost {
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}

	resp, err := b.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("binance fetch: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("binance read: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("binance error %d: %s", resp.StatusCode, string(respBody))
	}
	return respBody, nil
}

func (b *BinanceBroker) toOrder(resp *binanceOrderResp) *Order {
	price, _ := strconv.ParseFloat(resp.Price, 64)
	qty, _ := strconv.ParseFloat(resp.OrigQty, 64)
	filled, _ := strconv.ParseFloat(resp.ExecutedQty, 64)
	avgPrice, _ := strconv.ParseFloat(resp.AvgPrice, 64)

	status := StatusPending
	switch resp.Status {
	case "NEW":
		status = StatusSubmitted
	case "PARTIALLY_FILLED":
		status = StatusPartial
	case "FILLED":
		status = StatusFilled
	case "CANCELED", "EXPIRED":
		status = StatusCancelled
	case "REJECTED":
		status = StatusRejected
	}

	return &Order{
		OrderID:      strconv.FormatInt(resp.OrderID, 10),
		Symbol:       resp.Symbol,
		Side:         OrderSide(strings.ToLower(resp.Side)),
		Type:         OrderType(strings.ToLower(resp.Type)),
		Price:        price,
		Quantity:     qty,
		FilledQty:    filled,
		FilledPrice:  avgPrice,
		Status:       status,
		RejectReason: resp.RejectReason,
		CreatedAt:    time.Now(),
	}
}
