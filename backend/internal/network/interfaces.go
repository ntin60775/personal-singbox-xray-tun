package network

import (
	"fmt"
	"net"
)

// InterfaceAddr holds a network interface name and its associated addresses.
type InterfaceAddr struct {
	Name      string   `json:"name"`
	Addresses []string `json:"addresses"`
}

// ListInterfaceAddresses returns all non-loopback interfaces with their addresses.
func ListInterfaceAddresses() ([]InterfaceAddr, error) {
	ifaces, err := net.Interfaces()
	if err != nil {
		return nil, fmt.Errorf("list interfaces: %w", err)
	}

	var result []InterfaceAddr
	for _, iface := range ifaces {
		if iface.Flags&net.FlagLoopback != 0 {
			continue
		}
		addrs, err := InterfaceAddresses(iface.Name)
		if err != nil {
			return nil, fmt.Errorf("addresses for %s: %w", iface.Name, err)
		}
		if len(addrs) == 0 {
			continue
		}
		result = append(result, InterfaceAddr{
			Name:      iface.Name,
			Addresses: addrs,
		})
	}
	return result, nil
}

// InterfaceAddresses returns the IP addresses assigned to the named interface.
func InterfaceAddresses(name string) ([]string, error) {
	iface, err := net.InterfaceByName(name)
	if err != nil {
		return nil, fmt.Errorf("interface %s: %w", name, err)
	}
	addrs, err := iface.Addrs()
	if err != nil {
		return nil, fmt.Errorf("addrs for %s: %w", name, err)
	}
	var result []string
	for _, a := range addrs {
		result = append(result, a.String())
	}
	return result, nil
}
