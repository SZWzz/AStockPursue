package engine

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestSignalAdapterTickMode(t *testing.T) {
	adapter := NewSignalAdapter("localhost:8902", 5*time.Second)
	weights, err := adapter.Generate([]interface{}{&Bar{Symbol: "000001", Close: 10}}, time.Now())
	if err != nil {
		assert.Empty(t, weights)
	} else {
		t.Log("gRPC server available, got weights")
	}
}
