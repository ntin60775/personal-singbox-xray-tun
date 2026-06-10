package shell

import (
	"fmt"
	"strings"
)

// IPRuleAdd adds an ip rule.
// Example: IPRuleAdd("add", "fwmark", "1", "table", "100")
func IPRuleAdd(args ...string) error {
	return ipRun(append([]string{"rule", "add"}, args...)...)
}

// IPRouteAdd adds an ip route.
// Example: IPRouteAdd("default", "dev", "tun0", "table", "100")
func IPRouteAdd(args ...string) error {
	return ipRun(append([]string{"route", "add"}, args...)...)
}

// IPLinkSet sets ip link properties.
// Example: IPLinkSet("tun0", "up")
func IPLinkSet(args ...string) error {
	return ipRun(append([]string{"link", "set"}, args...)...)
}

// IPTuntapAdd creates a TUN/TAP device.
// Example: IPTuntapAdd("tun0", "tun")
func IPTuntapAdd(name string, mode string) error {
	return ipRun("tuntap", "add", "dev", name, "mode", mode)
}

// IPAddrShow returns the addresses of a device.
// Example: IPAddrShow("tun0")
func IPAddrShow(dev string) (string, error) {
	return Run("ip", "addr", "show", "dev", dev)
}

// ipRun executes an ip command with the given arguments and returns an error on failure.
func ipRun(args ...string) error {
	cmdLine := "ip " + strings.Join(args, " ")
	stdout, exitCode, err := RunWithEnv("ip", args, nil)
	if err != nil {
		return fmt.Errorf("%s: %w", cmdLine, err)
	}
	if exitCode != 0 {
		return fmt.Errorf("%s: exit code %d: %s", cmdLine, exitCode, stdout)
	}
	return nil
}
