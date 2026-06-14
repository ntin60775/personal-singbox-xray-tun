package runtime

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// CreateTun creates a TUN device using ip tuntap.
// If the device already exists (e.g. from a crashed previous run),
// it is deleted first to avoid "name is duplicate" errors.
// MTU is set separately via ip link after creation (ip tuntap does not support mtu).
func CreateTun(name string, mtu int) error {
	// Verify /dev/net/tun exists.
	if _, err := os.Stat("/dev/net/tun"); err != nil {
		return fmt.Errorf("/dev/net/tun not found; TUN kernel module may be missing: %w", err)
	}

	// Clean up stale device from a previous run that wasn't properly torn down.
	if CheckTunExists(name) {
		delCmd := exec.Command("ip", "link", "del", name)
		if out, err := delCmd.CombinedOutput(); err != nil {
			return fmt.Errorf("ip link del %s (stale device): %s: %w", name, strings.TrimSpace(string(out)), err)
		}
	}

	// Create the device (ip tuntap add does NOT support mtu parameter).
	cmd := exec.Command("ip", "tuntap", "add", "dev", name, "mode", "tun")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("ip tuntap add %s: %s: %w", name, strings.TrimSpace(string(out)), err)
	}

	// Set MTU separately.
	if mtu > 0 {
		mtuCmd := exec.Command("ip", "link", "set", "dev", name, "mtu", fmt.Sprintf("%d", mtu))
		if out, err := mtuCmd.CombinedOutput(); err != nil {
			return fmt.Errorf("ip link set mtu %s: %s: %w", name, strings.TrimSpace(string(out)), err)
		}
	}

	return nil
}

// SetupPolicyRouting configures routing for the TUN interface:
// brings the interface up, assigns a standard /30 address, sets up a
// default route in a dedicated table, and adds an ip rule for unmarked traffic.
func SetupPolicyRouting(tunName string, fwmark int, table int) error {
	// Standard TUN address: 172.19.0.1/30
	tunAddress := "172.19.0.1/30"

	// Bring the interface up.
	if out, err := exec.Command("ip", "link", "set", "dev", tunName, "up").CombinedOutput(); err != nil {
		return fmt.Errorf("bring tun %s up: %s: %w", tunName, strings.TrimSpace(string(out)), err)
	}

	// Assign address.
	if out, err := exec.Command("ip", "address", "add", tunAddress, "dev", tunName).CombinedOutput(); err != nil {
		return fmt.Errorf("assign address %s to %s: %s: %w", tunAddress, tunName, strings.TrimSpace(string(out)), err)
	}

	// Default route in the dedicated table.
	cmd := exec.Command("ip", "route", "replace", "table", fmt.Sprintf("%d", table), "default", "dev", tunName)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("set default route table %d via %s: %s: %w", table, tunName, strings.TrimSpace(string(out)), err)
	}

	// Ip rule: traffic without the fwmark uses the dedicated table.
	rulePref := 100
	exec.Command("ip", "rule", "del",
		"pref", fmt.Sprintf("%d", rulePref),
		"not", "fwmark", fmt.Sprintf("%d", fwmark),
		"table", fmt.Sprintf("%d", table)).Run()
	cmd = exec.Command("ip", "rule", "add",
		"pref", fmt.Sprintf("%d", rulePref),
		"not", "fwmark", fmt.Sprintf("%d", fwmark),
		"table", fmt.Sprintf("%d", table))
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("add ip rule: %s: %w", strings.TrimSpace(string(out)), err)
	}

	// Flush route cache.
	exec.Command("ip", "route", "flush", "cache").Run()

	return nil
}

// TeardownTun removes the policy routing rules, flushes the dedicated table,
// and deletes the TUN interface.
func TeardownTun(tunName string, table int, fwmark int) error {
	rulePref := 100

	// Remove ip rule.
	exec.Command("ip", "rule", "del",
		"pref", fmt.Sprintf("%d", rulePref),
		"not", "fwmark", fmt.Sprintf("%d", fwmark),
		"table", fmt.Sprintf("%d", table)).Run()

	// Flush dedicated routing table.
	exec.Command("ip", "route", "flush", "table", fmt.Sprintf("%d", table)).Run()

	// Flush route cache.
	exec.Command("ip", "route", "flush", "cache").Run()

	// Delete TUN interface.
	if tunName != "" {
		out, err := exec.Command("ip", "link", "delete", tunName).CombinedOutput()
		if err != nil {
			return fmt.Errorf("delete TUN interface %s: %s: %w", tunName, strings.TrimSpace(string(out)), err)
		}
	}

	return nil
}

// CheckTunExists returns true if the named network interface exists.
func CheckTunExists(name string) bool {
	_, err := os.Stat("/sys/class/net/" + name)
	return err == nil
}

// ResolveSystemDNS reads nameserver entries from /etc/resolv.conf.
func ResolveSystemDNS() ([]string, error) {
	f, err := os.Open("/etc/resolv.conf")
	if err != nil {
		return nil, fmt.Errorf("open /etc/resolv.conf: %w", err)
	}
	defer f.Close()

	var servers []string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "nameserver") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				servers = append(servers, fields[1])
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return servers, fmt.Errorf("read /etc/resolv.conf: %w", err)
	}
	return servers, nil
}

// BackupResolvConf copies the current /etc/resolv.conf to backupPath.
func BackupResolvConf(backupPath string) error {
	src, err := os.ReadFile("/etc/resolv.conf")
	if err != nil {
		return fmt.Errorf("read /etc/resolv.conf for backup: %w", err)
	}
	if err := os.WriteFile(backupPath, src, 0644); err != nil {
		return fmt.Errorf("write resolv backup to %s: %w", backupPath, err)
	}
	return nil
}

// WriteTunResolvConf writes a TUN-mode resolv.conf to the given path.
func WriteTunResolvConf(targetPath string, nameservers []string) error {
	var sb strings.Builder
	sb.WriteString("# Managed by subvostd\n")
	for _, ns := range nameservers {
		sb.WriteString("nameserver ")
		sb.WriteString(ns)
		sb.WriteString("\n")
	}
	sb.WriteString("options timeout:2 attempts:2\n")

	if err := os.WriteFile(targetPath, []byte(sb.String()), 0644); err != nil {
		return fmt.Errorf("write %s: %w", targetPath, err)
	}
	return nil
}

// RestoreResolvConf restores /etc/resolv.conf from the backup file.
func RestoreResolvConf(backupPath string) error {
	if _, err := os.Stat(backupPath); os.IsNotExist(err) {
		return nil
	}
	src, err := os.ReadFile(backupPath)
	if err != nil {
		return fmt.Errorf("read resolv backup %s: %w", backupPath, err)
	}
	if err := os.WriteFile("/etc/resolv.conf", src, 0644); err != nil {
		return fmt.Errorf("restore /etc/resolv.conf from backup: %w", err)
	}
	return nil
}

// DetectDefaultInterface extracts the default IPv4 route's interface and gateway.
func DetectDefaultInterface() (string, string, error) {
	cmd := exec.Command("ip", "-4", "route", "show", "default")
	out, err := cmd.Output()
	if err != nil {
		return "", "", fmt.Errorf("no default IPv4 route: %w", err)
	}
	line := strings.TrimSpace(strings.SplitN(string(out), "\n", 2)[0])

	fields := strings.Fields(line)
	iface := ""
	gateway := ""
	for i, f := range fields {
		if f == "dev" && i+1 < len(fields) {
			iface = fields[i+1]
		}
		if f == "via" && i+1 < len(fields) {
			gateway = fields[i+1]
		}
	}
	if iface == "" {
		return "", "", fmt.Errorf("cannot determine interface from default route: %s", line)
	}
	return iface, gateway, nil
}
