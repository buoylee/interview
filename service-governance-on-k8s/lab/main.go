// echolab — minimal HTTP/2 (h2c) echo server + client to SEE k8s long-connection pinning.
//
// Why h2c and not literal gRPC: gRPC runs over HTTP/2, and the pinning we want to
// observe is a *connection-level* effect — one TCP/HTTP-2 connection gets pinned by
// kube-proxy (L4) to a single pod, so every request multiplexed on it lands there.
// h2c reproduces this identically with zero protobuf codegen. Each mode below maps
// to a gRPC knob:
//
//	pinned  ≈ gRPC default pick_first against a ClusterIP Service  (BROKEN: all → 1 pod)
//	spread  ≈ gRPC round_robin over a headless Service (dns:///)   (FIX: spread across pods)
//
// See README.md for the full walkthrough.
package main

import (
	"crypto/tls"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"golang.org/x/net/http2"
	"golang.org/x/net/http2/h2c"
)

func main() {
	if len(os.Args) < 2 {
		usage()
	}
	switch os.Args[1] {
	case "server":
		must(runServer())
	case "pinned": // pinned <url> <n>
		if len(os.Args) != 4 {
			usage()
		}
		must(runPinned(os.Args[2], atoi(os.Args[3])))
	case "spread": // spread <headless-host> <port> <n>
		if len(os.Args) != 5 {
			usage()
		}
		must(runSpread(os.Args[2], os.Args[3], atoi(os.Args[4])))
	default:
		usage()
	}
}

// runServer serves the pod's hostname. h2c.NewHandler also answers plain HTTP/1.1
// (so the kubelet httpGet readiness probe works), and HTTP/2 prior-knowledge clients.
func runServer() error {
	host, _ := os.Hostname()
	h := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, host)
	})
	srv := &http.Server{
		Addr:    ":8080",
		Handler: h2c.NewHandler(h, &http2.Server{}),
	}
	fmt.Fprintf(os.Stderr, "echolab server listening :8080 hostname=%s\n", host)
	return srv.ListenAndServe()
}

// h2cClient returns an *http.Client speaking HTTP/2 cleartext. If pinIP != "",
// every connection is dialed to that exact IP:port — used to open one connection
// per pod IP in the round-robin (spread) demo.
func h2cClient(pinIP string) *http.Client {
	tr := &http2.Transport{
		AllowHTTP: true,
		DialTLS: func(network, addr string, _ *tls.Config) (net.Conn, error) {
			if pinIP != "" {
				addr = pinIP
			}
			return net.Dial(network, addr)
		},
	}
	return &http.Client{Transport: tr, Timeout: 5 * time.Second}
}

func get(c *http.Client, url string) (string, error) {
	resp, err := c.Get(url)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	b, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(b)), nil
}

// runPinned: ONE client = ONE HTTP/2 connection to the ClusterIP VIP. kube-proxy
// pins that connection to a single pod, so all N requests land on the same pod.
// gRPC equivalent: the default pick_first policy against a ClusterIP Service.
func runPinned(url string, n int) error {
	c := h2cClient("")
	tally := map[string]int{}
	for i := 0; i < n; i++ {
		host, err := get(c, url)
		if err != nil {
			return err
		}
		tally[host]++
	}
	printTally(fmt.Sprintf("PINNED — one H2 conn to %s", url), n, tally)
	return nil
}

// runSpread: resolve the HEADLESS service (DNS returns all pod IPs) → open one
// connection per IP → round-robin. gRPC equivalent: round_robin over dns:///headless.
func runSpread(headlessHost, port string, n int) error {
	ips, err := net.LookupHost(headlessHost)
	if err != nil {
		return err
	}
	sort.Strings(ips)
	if len(ips) == 0 {
		return fmt.Errorf("no IPs resolved for %s (is it a headless Service?)", headlessHost)
	}
	clients := make([]*http.Client, len(ips))
	for i, ip := range ips {
		clients[i] = h2cClient(net.JoinHostPort(ip, port))
	}
	url := "http://" + net.JoinHostPort(headlessHost, port) + "/"
	tally := map[string]int{}
	for i := 0; i < n; i++ {
		host, err := get(clients[i%len(clients)], url)
		if err != nil {
			return err
		}
		tally[host]++
	}
	fmt.Printf("resolved %d pod IP(s) from %s: %v\n", len(ips), headlessHost, ips)
	printTally("SPREAD — one conn per pod IP, round-robin", n, tally)
	return nil
}

func printTally(title string, n int, tally map[string]int) {
	fmt.Printf("\n=== %s ===\n%d requests →\n", title, n)
	keys := make([]string, 0, len(tally))
	for k := range tally {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Printf("  %-44s %d\n", k, tally[k])
	}
	fmt.Printf("(%d distinct pod[s] hit)\n", len(tally))
}

func usage() {
	fmt.Fprintln(os.Stderr, `usage:
  echolab server
  echolab pinned <url> <n>                  # pinned http://echo-clusterip:8080/ 30
  echolab spread <headless-host> <port> <n> # spread echo-headless 8080 30`)
	os.Exit(2)
}

func must(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func atoi(s string) int {
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			fmt.Fprintln(os.Stderr, "not a number:", s)
			os.Exit(2)
		}
		n = n*10 + int(c-'0')
	}
	return n
}
