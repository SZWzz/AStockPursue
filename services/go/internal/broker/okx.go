package broker

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"
)

func init() {
	Register("okx", NewOKXBroker)
}

// OKXBroker implements Broker for OKX perpetual swaps.
// Uses OKX REST API v5 with HMAC-SHA256 signing.
type OKXBroker struct {
	apiKey     string
	secretKey  string
	passphrase string
	baseURL    string
	client     *http.Client
}

type okxOrderResp struct {
	Code string         `json:"code"`
	Msg  string         `json:"msg"`
	Data []okxOrderData `json:"data"`
}

type okxOrderData struct {
	OrdID     string `json:"ordId"`
	InstID    string `json:"instId"`
	Side      string `json:"side"`
	OrdType   string `json:"ordType"`
	Px        string `json:"px"`
	Sz        string `json:"sz"`
	AccFillSz string `json:"accFillSz"`
	AvgPx     string `json:"avgPx"`
	State     string `json:"state"`
}

type okxBalanceResp struct {
	Code string           `json:"code"`
	Data []okxBalanceData `json:"data"`
}

type okxBalanceData struct {
	Details []okxBalanceDetail `json:"details"`
}

type okxBalanceDetail struct {
	Ccy       string `json:"ccy"`
	Eq        string `json:"eq"`
	AvailEq   string `json:"availEq"`
	FrozenBal string `json:"frozenBal"`
}

type okxPositionResp struct {
	Code string            `json:"code"`
	Data []okxPositionData `json:"data"`
}

type okxPositionData struct {
	InstID string `json:"instId"`
	Pos    string `json:"pos"`
	AvgPx  string `json:"avgPx"`
	MarkPx string `json:"markPx"`
	Upl    string `json:"upl"`
}

type okxPlaceOrderReq struct {
	InstID  string  `json:"instId"`
	TdMode  string  `json:"tdMode"`
	Side    string  `json:"side"`
	OrdType string  `json:"ordType"`
	Sz      string  `json:"sz"`
	Px      *string `json:"px,omitempty"`
}

type okxCancelOrderReq struct {
	InstID string `json:"instId"`
	OrdID  string `json:"ordId"`
}

// NewOKXBroker creates a new OKX broker.
// The base URL defaults to "https://www.okx.com".
// Set OKX_API_URL env var to override the URL via config.Load().
func NewOKXBroker(cfg BrokerConfig) (Broker, error) {
	baseURL := "https://www.okx.com"
	if cfg.Testnet {
		baseURL = "https://www.okx.com" // OKX demo uses same URL but with demo trading enabled in account
	}
	return &OKXBroker{
		apiKey:     cfg.APIKey,
		secretKey:  cfg.Secret,
		passphrase: cfg.Passphrase,
		baseURL:    baseURL,
		client:     &http.Client{Timeout: 30 * time.Second},
	}, nil
}

func (b *OKXBroker) Name() string { return "okx" }

func (b *OKXBroker) TestConnection(ctx context.Context) error {
	_, err := b.signedGet(ctx, "/api/v5/account/balance", "")
	return err
}

func (b *OKXBroker) GetFeeRate(symbol string) FeeRate {
	return FeeRate{Maker: 0.0002, Taker: 0.0005}
}

// ── Order management ──────────────────────────────────────────────

func (b *OKXBroker) PlaceOrder(ctx context.Context, symbol string, side OrderSide, orderType OrderType, quantity, price float64) (*Order, error) {
	instID := strings.ToUpper(symbol) + "-SWAP"
	req := okxPlaceOrderReq{
		InstID:  instID,
		TdMode:  "cross",
		Side:    strings.ToLower(string(side)),
		OrdType: strings.ToLower(string(orderType)),
		Sz:      strconv.FormatFloat(quantity, 'f', -1, 64),
	}
	if orderType == Limit && price > 0 {
		pxStr := strconv.FormatFloat(price, 'f', -1, 64)
		req.Px = &pxStr
	}
	bodyBytes, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("okx marshal order request: %w", err)
	}
	body := string(bodyBytes)

	respBody, err := b.signedPostOKX(ctx, "/api/v5/trade/order", body)
	if err != nil {
		return nil, err
	}
	var resp okxOrderResp
	if err := json.Unmarshal(respBody, &resp); err != nil {
		return nil, fmt.Errorf("okx parse order response: %w", err)
	}
	if resp.Code != "0" {
		return nil, fmt.Errorf("okx place order: %s", resp.Msg)
	}
	if len(resp.Data) == 0 {
		return nil, fmt.Errorf("okx place order: no data returned")
	}
	d := resp.Data[0]
	return b.toOrder(&d)
}

func (b *OKXBroker) CancelOrder(ctx context.Context, orderID, symbol string) error {
	instID := strings.ToUpper(symbol) + "-SWAP"
	req := okxCancelOrderReq{
		InstID: instID,
		OrdID:  orderID,
	}
	bodyBytes, err := json.Marshal(req)
	if err != nil {
		return fmt.Errorf("okx marshal cancel request: %w", err)
	}
	body := string(bodyBytes)
	respBody, err := b.signedPostOKX(ctx, "/api/v5/trade/cancel-order", body)
	if err != nil {
		return err
	}
	var resp okxOrderResp
	if err := json.Unmarshal(respBody, &resp); err != nil {
		return fmt.Errorf("okx parse cancel response: %w", err)
	}
	if resp.Code != "0" {
		return fmt.Errorf("okx cancel order: %s", resp.Msg)
	}
	return nil
}

func (b *OKXBroker) GetOrder(ctx context.Context, orderID, symbol string) (*Order, error) {
	instID := strings.ToUpper(symbol) + "-SWAP"
	path := fmt.Sprintf("/api/v5/trade/order?instId=%s&ordId=%s", instID, orderID)
	body, err := b.signedGet(ctx, path, "")
	if err != nil {
		return nil, err
	}
	var resp okxOrderResp
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("okx parse order: %w", err)
	}
	if len(resp.Data) == 0 {
		return nil, fmt.Errorf("okx order not found: %s", orderID)
	}
	return b.toOrder(&resp.Data[0])
}

func (b *OKXBroker) GetOpenOrders(ctx context.Context, symbol string) ([]*Order, error) {
	path := "/api/v5/trade/orders-pending"
	if symbol != "" {
		path += "?instId=" + strings.ToUpper(symbol) + "-SWAP"
	}
	body, err := b.signedGet(ctx, path, "")
	if err != nil {
		return nil, err
	}
	var resp okxOrderResp
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("okx parse open orders: %w", err)
	}
	orders := make([]*Order, len(resp.Data))
	for i := range resp.Data {
		o, err := b.toOrder(&resp.Data[i])
		if err != nil {
			return nil, err
		}
		orders[i] = o
	}
	return orders, nil
}

// ── Position & balance ────────────────────────────────────────────

func (b *OKXBroker) GetPosition(ctx context.Context, symbol string) (*Position, error) {
	instID := strings.ToUpper(symbol) + "-SWAP"
	body, err := b.signedGet(ctx, "/api/v5/account/positions?instId="+instID, "")
	if err != nil {
		return nil, err
	}
	var resp okxPositionResp
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("okx parse positions: %w", err)
	}
	for _, d := range resp.Data {
		if d.InstID == instID {
			return b.toPosition(&d)
		}
	}
	return &Position{Symbol: instID}, nil
}

func (b *OKXBroker) GetPositions(ctx context.Context) ([]*Position, error) {
	body, err := b.signedGet(ctx, "/api/v5/account/positions?instType=SWAP", "")
	if err != nil {
		return nil, err
	}
	var resp okxPositionResp
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("okx parse positions: %w", err)
	}
	positions := make([]*Position, 0, len(resp.Data))
	parseErrors := 0
	for i := range resp.Data {
		qty, err := safeParseFloat(resp.Data[i].Pos)
		if err != nil {
			log.Printf("okx: parse Pos %q: %v", resp.Data[i].Pos, err)
			parseErrors++
			continue
		}
		if qty == 0 {
			continue
		}
		p, err := b.toPosition(&resp.Data[i])
		if err != nil {
			log.Printf("okx: parse position: %v", err)
			parseErrors++
			continue
		}
		positions = append(positions, p)
	}
	if parseErrors > 0 {
		log.Printf("okx: GetPositions skipped %d position(s) due to parse errors", parseErrors)
	}
	return positions, nil
}

func (b *OKXBroker) GetBalance(ctx context.Context) (*Balance, error) {
	body, err := b.signedGet(ctx, "/api/v5/account/balance", "")
	if err != nil {
		return nil, err
	}
	var resp okxBalanceResp
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("okx parse balance: %w", err)
	}
	for _, d := range resp.Data {
		for _, det := range d.Details {
			if det.Ccy == "USDT" {
				total, err := safeParseFloat(det.Eq)
				if err != nil {
					return nil, fmt.Errorf("okx: parse balance total: %w", err)
				}
				avail, err := safeParseFloat(det.AvailEq)
				if err != nil {
					return nil, fmt.Errorf("okx: parse balance available: %w", err)
				}
				frozen, err := safeParseFloat(det.FrozenBal)
				if err != nil {
					return nil, fmt.Errorf("okx: parse balance frozen: %w", err)
				}
				return &Balance{Total: total, Available: avail, Frozen: frozen, Currency: "USDT"}, nil
			}
		}
	}
	return &Balance{Currency: "USDT"}, nil
}

// ── Private helpers ───────────────────────────────────────────────

func (b *OKXBroker) sign(method, path, body string) (timestamp, sign string) {
	ts := time.Now().UTC().Format("2006-01-02T15:04:05.000Z")
	preHash := ts + method + path + body
	mac := hmac.New(sha256.New, []byte(b.secretKey))
	_, _ = mac.Write([]byte(preHash))
	return ts, base64.StdEncoding.EncodeToString(mac.Sum(nil))
}

func (b *OKXBroker) signedGet(ctx context.Context, path, body string) ([]byte, error) {
	return b.signedRequest(ctx, http.MethodGet, path, body)
}

func (b *OKXBroker) signedPostOKX(ctx context.Context, path, body string) ([]byte, error) {
	return b.signedRequest(ctx, http.MethodPost, path, body)
}

func (b *OKXBroker) signedRequest(ctx context.Context, method, path, body string) ([]byte, error) {
	if b.apiKey == "" || b.secretKey == "" {
		return nil, fmt.Errorf("okx: API key and secret required")
	}
	ts, sign := b.sign(method, path, body)

	req, err := http.NewRequestWithContext(ctx, method, b.baseURL+path, strings.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("okx request: %w", err)
	}
	req.Header.Set("OK-ACCESS-KEY", b.apiKey)
	req.Header.Set("OK-ACCESS-SIGN", sign)
	req.Header.Set("OK-ACCESS-TIMESTAMP", ts)
	req.Header.Set("OK-ACCESS-PASSPHRASE", b.passphrase)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := b.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("okx fetch: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("okx read: %w", err)
	}
	return respBody, nil
}

func (b *OKXBroker) toOrder(d *okxOrderData) (*Order, error) {
	price, err := safeParseFloat(d.Px)
	if err != nil {
		return nil, fmt.Errorf("okx: parse order price: %w", err)
	}
	qty, err := safeParseFloat(d.Sz)
	if err != nil {
		return nil, fmt.Errorf("okx: parse order qty: %w", err)
	}
	filled, err := safeParseFloat(d.AccFillSz)
	if err != nil {
		return nil, fmt.Errorf("okx: parse order filled: %w", err)
	}
	avgPrice, err := safeParseFloat(d.AvgPx)
	if err != nil {
		return nil, fmt.Errorf("okx: parse order avg price: %w", err)
	}

	status := StatusPending
	switch d.State {
	case "live":
		status = StatusSubmitted
	case "partially_filled":
		status = StatusPartial
	case "filled":
		status = StatusFilled
	case "canceled":
		status = StatusCancelled
	}

	return &Order{
		OrderID:     d.OrdID,
		Symbol:      d.InstID,
		Side:        OrderSide(strings.ToLower(d.Side)),
		Type:        OrderType(strings.ToLower(d.OrdType)),
		Price:       price,
		Quantity:    qty,
		FilledQty:   filled,
		FilledPrice: avgPrice,
		Status:      status,
		CreatedAt:   time.Now(),
	}, nil
}

func (b *OKXBroker) toPosition(d *okxPositionData) (*Position, error) {
	qty, err := safeParseFloat(d.Pos)
	if err != nil {
		return nil, fmt.Errorf("okx: parse position qty: %w", err)
	}
	avgPrice, err := safeParseFloat(d.AvgPx)
	if err != nil {
		return nil, fmt.Errorf("okx: parse position avg price: %w", err)
	}
	markPrice, err := safeParseFloat(d.MarkPx)
	if err != nil {
		return nil, fmt.Errorf("okx: parse position mark price: %w", err)
	}
	upnl, err := safeParseFloat(d.Upl)
	if err != nil {
		return nil, fmt.Errorf("okx: parse position upl: %w", err)
	}
	return &Position{
		Symbol:        d.InstID,
		Quantity:      qty,
		AvgPrice:      avgPrice,
		CurrentPrice:  markPrice,
		UnrealizedPnL: upnl,
	}, nil
}
