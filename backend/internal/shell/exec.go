package shell

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// Run executes a command and returns combined stdout+stderr as a string.
// Returns an error if the command exits with a non-zero status.
func Run(name string, args ...string) (string, error) {
	stdout, exitCode, err := RunWithEnv(name, args, nil)
	if err != nil {
		return stdout, err
	}
	if exitCode != 0 {
		return stdout, fmt.Errorf("command %s exited with code %d", name, exitCode)
	}
	return stdout, nil
}

// RunWithEnv executes a command with additional environment variables and returns
// stdout (as string), exit code, and any execution error.
// Env vars are set in addition to the current process environment.
func RunWithEnv(name string, args []string, env map[string]string) (string, int, error) {
	cmd := exec.Command(name, args...)

	// Build environment: inherit current + add extras.
	if len(env) > 0 {
		cmdEnv := os.Environ()
		for k, v := range env {
			cmdEnv = append(cmdEnv, k+"="+v)
		}
		cmd.Env = cmdEnv
	}

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	exitCode := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			return "", -1, fmt.Errorf("running %s: %w", cmdString(name, args), err)
		}
	}

	output := stdoutBuf.String()
	if stderrBuf.Len() > 0 {
		if output != "" {
			output += "\n"
		}
		output += stderrBuf.String()
	}

	return strings.TrimRight(output, "\n"), exitCode, nil
}

// RunAsRoot executes a command as root. If the current process is not running
// as root, it prepends "pkexec" to elevate privileges.
func RunAsRoot(name string, args []string, env map[string]string) (string, int, error) {
	if os.Geteuid() == 0 {
		return RunWithEnv(name, args, env)
	}

	// Prepend pkexec.
	pkexecArgs := make([]string, 0, 1+len(args))
	pkexecArgs = append(pkexecArgs, name)
	pkexecArgs = append(pkexecArgs, args...)
	return RunWithEnv("pkexec", pkexecArgs, env)
}

// cmdString builds a human-readable command string for error messages.
func cmdString(name string, args []string) string {
	parts := make([]string, 0, 1+len(args))
	parts = append(parts, name)
	parts = append(parts, args...)
	return strings.Join(parts, " ")
}
