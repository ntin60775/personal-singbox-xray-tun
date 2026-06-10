package network

import (
	"fmt"
	"net"
	"time"

	"github.com/subvost/xray-tun/backend/internal/domain"
)

// TCPPing dials host:port and measures the time to establish a TCP connection.
// Returns ok=false if the connection failed, with latencyMs undefined.
func TCPPing(host string, port int, timeout time.Duration) (ok bool, latencyMs float64, err error) {
	start := time.Now()

	conn, dialErr := net.DialTimeout("tcp", net.JoinHostPort(host, fmt.Sprint(port)), timeout)
	elapsed := time.Since(start)

	if dialErr != nil {
		return false, 0, nil
	}
	conn.Close()
	return true, float64(elapsed.Microseconds()) / 1000.0, nil
}

// PingNode extracts address and port from node.Normalized and performs a TCP ping.
func PingNode(node *domain.Node, timeout time.Duration) (latencyMs float64, err error) {
	if node == nil {
		return 0, fmt.Errorf("node is nil")
	}
	addr := node.Normalized
	if addr.Address == "" {
		return 0, fmt.Errorf("node %s has no address", node.ID)
	}
	if addr.Port == 0 {
		return 0, fmt.Errorf("node %s has no port", node.ID)
	}

	ok, lat, _ := TCPPing(addr.Address, addr.Port, timeout)
	if !ok {
		return 0, fmt.Errorf("tcp ping to %s:%d failed", addr.Address, addr.Port)
	}
	return lat, nil
}
