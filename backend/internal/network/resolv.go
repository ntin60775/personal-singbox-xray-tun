package network

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// ReadResolvConfNameservers parses /etc/resolv.conf and returns the list of
// nameserver addresses.
func ReadResolvConfNameservers() ([]string, error) {
	f, err := os.Open("/etc/resolv.conf")
	if err != nil {
		return nil, fmt.Errorf("open /etc/resolv.conf: %w", err)
	}
	defer f.Close()

	var nameservers []string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) >= 2 && fields[0] == "nameserver" {
			nameservers = append(nameservers, fields[1])
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("scan /etc/resolv.conf: %w", err)
	}
	return nameservers, nil
}
