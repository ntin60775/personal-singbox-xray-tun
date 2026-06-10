package rpc

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sync"

	"github.com/subvost/xray-tun/backend/internal/domain"
	"github.com/subvost/xray-tun/backend/internal/store"
)

// HandlerFunc is the signature for JSON-RPC method handlers.
// It receives the raw params JSON and returns the result value
// (which will be JSON-serialized) or an error.
type HandlerFunc func(params json.RawMessage) (interface{}, error)

// Server is a JSON-RPC server that communicates over stdin/stdout.
// It manages the application store, dispatches requests to registered
// handlers, and writes JSON responses to stdout.
type Server struct {
	paths       store.AppPaths
	projectRoot string
	store       *domain.Store
	handlers    map[string]HandlerFunc
	mu          sync.Mutex
	running     bool
}

// NewServer creates a Server with the given config home and project root.
// configHome is where the application data is stored (e.g. ~/.config).
// projectRoot is the repository root (for locating xray binary, scripts, etc.).
func NewServer(configHome, projectRoot string) *Server {
	paths := store.BuildAppPaths(configHome)
	s := &Server{
		paths:       paths,
		projectRoot: projectRoot,
		handlers:    make(map[string]HandlerFunc),
	}
	s.registerHandlers()
	return s
}

// Serve initializes the store and enters the request/response loop on
// stdin/stdout. It blocks until a "shutdown" method is received or
// stdin is closed. Returns nil on clean shutdown.
func (s *Server) Serve() error {
	s.mu.Lock()
	s.running = true
	s.mu.Unlock()

	// Initialize or load the store
	st, err := store.EnsureStoreInitialized(s.paths)
	if err != nil {
		return fmt.Errorf("init store: %w", err)
	}
	s.store = st

	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(nil, 10*1024*1024) // 10 MB max line

	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}

		var req Request
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			s.writeError(0, ErrParse, "Parse error: "+err.Error())
			continue
		}

		// Shutdown is handled directly in the loop
		if req.Method == "shutdown" {
			s.writeResult(req.ID, map[string]bool{"ok": true})
			break
		}

		s.dispatch(req)
	}

	if err := scanner.Err(); err != nil && err != io.EOF {
		return fmt.Errorf("stdin scan: %w", err)
	}
	return nil
}

// Shutdown marks the server as no longer running.
func (s *Server) Shutdown() {
	s.mu.Lock()
	s.running = false
	s.mu.Unlock()
}

// dispatch looks up the handler for the request method and invokes it.
func (s *Server) dispatch(req Request) {
	handler, ok := s.handlers[req.Method]
	if !ok {
		s.writeError(req.ID, ErrMethod, "Method not found: "+req.Method)
		return
	}

	result, err := handler(req.Params)
	if err != nil {
		s.writeError(req.ID, ErrInternal, err.Error())
		return
	}

	s.writeResult(req.ID, result)
}

// writeResult writes a successful JSON-RPC response to stdout.
func (s *Server) writeResult(id int64, result interface{}) {
	resp := Response{
		ID:     id,
		Result: result,
	}
	data, err := json.Marshal(resp)
	if err != nil {
		s.writeError(id, ErrInternal, "Marshal response: "+err.Error())
		return
	}
	fmt.Fprintf(os.Stdout, "%s\n", data)
}

// writeError writes a JSON-RPC error response to stdout.
func (s *Server) writeError(id int64, code int, message string) {
	resp := Response{
		ID: id,
		Error: &RPCError{
			Code:    code,
			Message: message,
		},
	}
	data, _ := json.Marshal(resp)
	fmt.Fprintf(os.Stdout, "%s\n", data)
}
