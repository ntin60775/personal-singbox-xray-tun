package runtime

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"
)

// StartXray launches the xray-core binary with the given configuration file.
// It locates the xray binary from standard system paths and PATH, creates a
// log file in the config directory's parent logs/ subdirectory, and returns
// the PID of the spawned process.
func StartXray(configPath string) (int, error) {
	if configPath == "" {
		return 0, fmt.Errorf("xray config path is empty")
	}

	xrayBinary := findXraySystem()
	if xrayBinary == "" {
		return 0, fmt.Errorf("xray binary not found (looked in /usr/local/bin/xray, /usr/bin/xray, and PATH)")
	}

	// Place logs adjacent to the config: <configDir>/../logs/
	configDir := filepath.Dir(configPath)
	logDir := filepath.Join(configDir, "..", "logs")
	if err := os.MkdirAll(logDir, 0755); err != nil {
		return 0, fmt.Errorf("create log directory %s: %w", logDir, err)
	}

	logPath := filepath.Join(logDir, "xray-subvost.log")
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return 0, fmt.Errorf("open xray log file %s: %w", logPath, err)
	}

	cmd := exec.Command(xrayBinary, "run", "-config", configPath)
	cmd.Stdout = logFile
	cmd.Stderr = logFile

	// Start in its own process group.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	if err := cmd.Start(); err != nil {
		logFile.Close()
		return 0, fmt.Errorf("start xray: %w", err)
	}

	return cmd.Process.Pid, nil
}

// StopXray sends SIGTERM to the given xray PID and waits up to 5 seconds
// for the process to exit. Falls back to SIGKILL if the process is still alive.
func StopXray(pid int) error {
	if pid <= 0 {
		return nil
	}

	process, err := os.FindProcess(pid)
	if err != nil {
		return nil
	}

	// Graceful shutdown via SIGTERM.
	if err := process.Signal(syscall.SIGTERM); err != nil {
		return nil
	}

	// Wait up to 5 seconds for graceful exit.
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if err := process.Signal(syscall.Signal(0)); err != nil {
			return nil
		}
		time.Sleep(200 * time.Millisecond)
	}

	// Force kill.
	process.Signal(syscall.SIGKILL)
	return nil
}

// IsXrayAlive checks whether a process with the given PID exists.
func IsXrayAlive(pid int) bool {
	if pid <= 0 {
		return false
	}
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return process.Signal(syscall.Signal(0)) == nil
}

// FindXrayBinary locates the xray binary. It searches projectRoot/bin/xray
// first, then standard system paths.
func FindXrayBinary(projectRoot string) string {
	candidates := []string{
		filepath.Join(projectRoot, "bin", "xray"),
		"/usr/local/bin/xray",
		"/usr/bin/xray",
	}

	for _, p := range candidates {
		info, err := os.Stat(p)
		if err == nil && !info.IsDir() && info.Mode()&0111 != 0 {
			return p
		}
	}

	if p, err := exec.LookPath("xray"); err == nil {
		return p
	}

	return ""
}


// findXraySystem locates xray from system paths only (no project root).
func findXraySystem() string {
	candidates := []string{
		"/usr/local/bin/xray",
		"/usr/bin/xray",
	}

	for _, p := range candidates {
		info, err := os.Stat(p)
		if err == nil && !info.IsDir() && info.Mode()&0111 != 0 {
			return p
		}
	}

	if p, err := exec.LookPath("xray"); err == nil {
		return p
	}

	return ""
}
// CaptureDiagnostics runs the capture-xray-tun-state.sh diagnostics script
// and returns its combined stdout/stderr as a string.
func CaptureDiagnostics(scriptPath string) (string, error) {
	if _, err := os.Stat(scriptPath); err != nil {
		return "", fmt.Errorf("diagnostics script not found at %s: %w", scriptPath, err)
	}

	cmd := exec.Command("bash", scriptPath)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return string(out), fmt.Errorf("diagnostics script failed: %w\n%s", err, string(out))
	}
	return string(out), nil
}
