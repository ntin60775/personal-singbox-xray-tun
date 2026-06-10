package rpc

import (
	"bufio"
	"encoding/json"
	"os"
	"os/exec"
	"strings"
	"testing"
)

// TestRPCIntegration spawns subvostd as a subprocess and validates
// JSON-RPC request/response flow over stdin/stdout.
//
// Prerequisites: subvostd binary must exist at ../subvostd relative
// to the backend/ directory. Build with:
//	cd backend && go build -o ../subvostd ./cmd/subvostd
func TestRPCIntegration(t *testing.T) {
	// go test runs from the package directory, so we need ../../../subvostd
	// to reach the project root where the binary lives.
	binPath := "../../../subvostd"
	if _, err := os.Stat(binPath); os.IsNotExist(err) {
		t.Skip("subvostd binary not found, build with: cd backend && go build -o ../subvostd ./cmd/subvostd")
	}

	// Use a temp config home to avoid touching the user's real store.
	configHome := t.TempDir() + "/config"

	cmd := exec.Command(binPath, "--mode", "serve", "--store", configHome)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		t.Fatalf("failed to create stdin pipe: %v", err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatalf("failed to create stdout pipe: %v", err)
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		t.Fatalf("failed to create stderr pipe: %v", err)
	}

	if err := cmd.Start(); err != nil {
		t.Fatalf("failed to start subvostd: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	// Drain stderr in background so the pipe doesn't fill up and block the server.
	go func() {
		sc := bufio.NewScanner(stderr)
		for sc.Scan() {
			// discard
		}
	}()

	reader := bufio.NewReader(stdout)

	// Helper: send a JSON-RPC request line and return the parsed Response.
	send := func(t *testing.T, request string) *Response {
		t.Helper()
		if _, err := stdin.Write([]byte(request + "\n")); err != nil {
			t.Fatalf("write to stdin: %v", err)
		}
		line, err := reader.ReadString('\n')
		if err != nil {
			t.Fatalf("read from stdout: %v", err)
		}
		line = strings.TrimSpace(line)
		if line == "" {
			t.Fatal("empty response line from server")
		}
		var resp Response
		if err := json.Unmarshal([]byte(line), &resp); err != nil {
			t.Fatalf("parse response %q: %v", line, err)
		}
		return &resp
	}

	// drainErr reads and discards the Error field; used when we expect an error.
	drainErr := func(t *testing.T, resp *Response) {
		t.Helper()
		if resp.Error == nil {
			return
		}
		t.Logf("server returned error: code=%d msg=%s", resp.Error.Code, resp.Error.Message)
	}

	t.Run("status", func(t *testing.T) {
		resp := send(t, `{"id":1,"method":"status","params":{}}`)
		if resp.Error != nil {
			t.Fatalf("RPC error: %s (code %d)", resp.Error.Message, resp.Error.Code)
		}
		result, ok := resp.Result.(map[string]interface{})
		if !ok {
			t.Fatalf("result is not a map: %T", resp.Result)
		}
		// active_node must exist (may be null when no node selected).
		if _, found := result["active_node"]; !found {
			t.Errorf("status response missing active_node, got keys: %v", keys(result))
		}
		if _, found := result["interfaces"]; !found {
			t.Errorf("status response missing interfaces")
		}
		if _, found := result["geodata_status"]; !found {
			t.Errorf("status response missing geodata_status")
		}
		_ = drainErr
	})

	t.Run("nodes.list", func(t *testing.T) {
		resp := send(t, `{"id":2,"method":"nodes.list","params":{}}`)
		if resp.Error != nil {
			t.Fatalf("RPC error: %s (code %d)", resp.Error.Message, resp.Error.Code)
		}
		result, ok := resp.Result.(map[string]interface{})
		if !ok {
			t.Fatalf("result is not a map: %T", resp.Result)
		}
		profilesRaw, ok := result["profiles"]
		if !ok {
			t.Fatal("nodes.list response missing profiles")
		}
		profiles, ok := profilesRaw.([]interface{})
		if !ok || len(profiles) == 0 {
			t.Fatalf("nodes.list: profiles is empty or not an array (type=%T)", profilesRaw)
		}
		// The default store has a "manual" profile at index 0.
		first, ok := profiles[0].(map[string]interface{})
		if !ok {
			t.Fatalf("profile item is not a map: %T", profiles[0])
		}
		id, ok := first["id"].(string)
		if !ok {
			t.Error("first profile missing id field")
		} else {
			t.Logf("first profile id: %s", id)
		}
	})

	t.Run("store.snapshot", func(t *testing.T) {
		resp := send(t, `{"id":3,"method":"store.snapshot","params":{}}`)
		if resp.Error != nil {
			t.Fatalf("RPC error: %s (code %d)", resp.Error.Message, resp.Error.Code)
		}
		result, ok := resp.Result.(map[string]interface{})
		if !ok {
			t.Fatalf("result is not a map: %T", resp.Result)
		}
		if _, ok := result["version"]; !ok {
			t.Error("store.snapshot response missing version")
		}
		if _, ok := result["profiles"]; !ok {
			t.Error("store.snapshot response missing profiles")
		}
	})

	t.Run("ping without params", func(t *testing.T) {
		resp := send(t, `{"id":4,"method":"ping","params":{}}`)
		// The ping handler unmarshals params; empty params should fail validation.
		if resp.Error == nil {
			t.Error("expected RPC error for ping without params, got success")
		}
	})

	t.Run("settings.get", func(t *testing.T) {
		resp := send(t, `{"id":5,"method":"settings.get","params":{}}`)
		_ = drainErr
		if resp.Error != nil {
			t.Fatalf("RPC error: %s (code %d)", resp.Error.Message, resp.Error.Code)
		}
		_, ok := resp.Result.(map[string]interface{})
		if !ok {
			t.Fatalf("result is not a map: %T", resp.Result)
		}
	})

	t.Run("unknown method", func(t *testing.T) {
		resp := send(t, `{"id":6,"method":"nonexistent.method","params":{}}`)
		if resp.Error == nil {
			t.Error("expected RPC error for unknown method, got success")
		} else {
			t.Logf("got expected error: code=%d msg=%s", resp.Error.Code, resp.Error.Message)
		}
	})

	t.Run("shutdown", func(t *testing.T) {
		resp := send(t, `{"id":99,"method":"shutdown","params":{}}`)
		if resp.Error != nil {
			t.Fatalf("RPC error: %s (code %d)", resp.Error.Message, resp.Error.Code)
		}
		result, ok := resp.Result.(map[string]interface{})
		if !ok {
			t.Fatalf("result is not a map: %T", resp.Result)
		}
		okVal, ok := result["ok"]
		if !ok || okVal != true {
			t.Errorf("shutdown: expected ok=true, got %v", okVal)
		}
	})

	// After shutdown, the process should exit cleanly.
	if err := cmd.Wait(); err != nil {
		t.Errorf("subvostd exited with error: %v", err)
	}
}

// keys returns the sorted keys of a map for diagnostic messages.
func keys(m map[string]interface{}) []string {
	k := make([]string, 0, len(m))
	for key := range m {
		k = append(k, key)
	}
	return k
}
