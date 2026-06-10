package runtime

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// ReadStateFile parses a key=value state file and returns the entries as a map.
// Lines starting with # are treated as comments and skipped.
func ReadStateFile(path string) map[string]string {
	state := make(map[string]string)
	f, err := os.Open(path)
	if err != nil {
		return state
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			val := strings.TrimSpace(parts[1])
			if key != "" {
				state[key] = val
			}
		}
	}
	return state
}

// WriteStateFile writes a key=value map to the given path.
func WriteStateFile(path string, state map[string]string) error {
	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("create state file %s: %w", path, err)
	}
	defer f.Close()

	for k, v := range state {
		if _, err := fmt.Fprintf(f, "%s=%s\n", k, v); err != nil {
			return fmt.Errorf("write entry %s: %w", k, err)
		}
	}
	return f.Sync()
}

// ClassifyOwnership determines whether a runtime state file belongs to the
// current installation. Possible return values:
//
//	"current" — the state belongs to this installation
//	"foreign" — the state belongs to a different installation
//	"unknown" — cannot determine ownership
func ClassifyOwnership(state map[string]string, installID, projectRoot string) string {
	if installID == "" {
		return "unknown"
	}

	stateInstallID := state["BUNDLE_INSTALL_ID"]
	stateProjectRoot := state["BUNDLE_PROJECT_ROOT_HINT"]

	// Strong match: same install ID.
	if stateInstallID != "" {
		if stateInstallID == installID {
			return "current"
		}
		// Different install ID is a clear foreign.
		return "foreign"
	}

	// No install ID in state. Fall back to project root match.
	if stateProjectRoot != "" && stateProjectRoot == projectRoot {
		return "current"
	}

	return "unknown"
}
