package network

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

// ReadTrafficCounters reads rx_bytes and tx_bytes from /sys/class/net/<iface>/statistics.
func ReadTrafficCounters(iface string) (rxBytes, txBytes uint64, err error) {
	if iface == "" {
		return 0, 0, fmt.Errorf("interface name is empty")
	}

	rx, err := readSysfsSingle(iface, "rx_bytes")
	if err != nil {
		return 0, 0, fmt.Errorf("read rx_bytes: %w", err)
	}
	tx, err := readSysfsSingle(iface, "tx_bytes")
	if err != nil {
		return 0, 0, fmt.Errorf("read tx_bytes: %w", err)
	}
	return rx, tx, nil
}

func readSysfsSingle(iface, stat string) (uint64, error) {
	path := "/sys/class/net/" + iface + "/statistics/" + stat
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, fmt.Errorf("read %s: %w", path, err)
	}
	return strconv.ParseUint(strings.TrimSpace(string(data)), 10, 64)
}
