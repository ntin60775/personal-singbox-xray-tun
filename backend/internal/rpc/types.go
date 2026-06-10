package rpc

import "encoding/json"

// Request is a JSON-RPC 2.0 request.
type Request struct {
	ID     int64           `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
}

// Response is a JSON-RPC 2.0 response.
type Response struct {
	ID     int64       `json:"id"`
	Result interface{} `json:"result,omitempty"`
	Error  *RPCError   `json:"error,omitempty"`
}

// RPCError is a JSON-RPC 2.0 error object.
type RPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// Standard JSON-RPC error codes.
const (
	ErrParse     = -32700
	ErrInvalid   = -32600
	ErrMethod    = -32601
	ErrInternal  = -32603
)
