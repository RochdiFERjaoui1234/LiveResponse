// Super SOAR Proxy Agent — runs as a hardened proxy on production targets.
// Enforces HMAC-SHA256 request authentication and strict command prefix allowlisting.
package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"time"
)

type CommandRequest struct {
	ID      string `json:"id"`
	Cmd     string `json:"cmd"`
	Timeout int    `json:"timeout"`
}

type CommandResponse struct {
	ID     string `json:"id"`
	Output string `json:"output"`
	Error  string `json:"error"`
}

// Strict allowlist of tactical response utilities
var allowedPrefixes = []string{
	"iptables ",
	"ip link ",
	"ifconfig ",
	"sysctl ",
	"usermod ",
	"passwd ",
	"kill ",
	"pkill ",
	"systemctl stop ",
	"systemctl restart ",
	"ufw ",
	"chmod 000 ",
	"mkdir -p /var/quarantine",
	"mv ",
	"touch /var/log/SUPER_SOAR",
}

func verifyHMAC(body []byte, sig string) bool {
	key := []byte(os.Getenv("SOAR_AGENT_KEY"))
	if len(key) == 0 {
		log.Println("[AGENT-WARN] SOAR_AGENT_KEY environment variable is not configured!")
		return false
	}
	mac := hmac.New(sha256.New, key)
	mac.Write(body)
	expectedSig := hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(strings.ToLower(sig)), []byte(strings.ToLower(expectedSig)))
}

func isCommandAllowed(cmd string) bool {
	trimmed := strings.TrimSpace(cmd)
	for _, prefix := range allowedPrefixes {
		if strings.HasPrefix(trimmed, prefix) {
			return true
		}
	}
	return false
}

func handleExec(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(io.LimitReader(r.Body, 8192))
	if err != nil {
		http.Error(w, "Payload Read Error", http.StatusBadRequest)
		return
	}

	sig := r.Header.Get("X-Soar-Signature")
	if !verifyHMAC(body, sig) {
		log.Printf("[AGENT-SECURITY] Unauthorized command attempt rejected from %s", r.RemoteAddr)
		http.Error(w, "Unauthorized: HMAC signature mismatch", http.StatusUnauthorized)
		return
	}

	var req CommandRequest
	if err := json.Unmarshal(body, &req); err != nil {
		http.Error(w, "Invalid JSON body", http.StatusBadRequest)
		return
	}

	if !isCommandAllowed(req.Cmd) {
		log.Printf("[AGENT-SECURITY] Blocked non-allowlisted command: %s", req.Cmd)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusForbidden)
		_ = json.NewEncoder(w).Encode(CommandResponse{
			ID:    req.ID,
			Error: "Command rejected: prefix not in security allowlist",
		})
		return
	}

	timeoutSec := req.Timeout
	if timeoutSec <= 0 || timeoutSec > 120 {
		timeoutSec = 30
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutSec)*time.Second)
	defer cancel()

	log.Printf("[AGENT-ACTION] Executing: %s", req.Cmd)
	cmd := exec.CommandContext(ctx, "bash", "-c", req.Cmd)
	out, err := cmd.CombinedOutput()

	resp := CommandResponse{
		ID:     req.ID,
		Output: string(out),
		Error:  "",
	}
	if err != nil {
		resp.Error = err.Error()
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

func main() {
	listenAddr := os.Getenv("SOAR_AGENT_ADDR")
	if listenAddr == "" {
		listenAddr = "127.0.0.1:8099"
	}

	http.HandleFunc("/exec", handleExec)
	http.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ready","agent":"super-soar-agent"}`))
	})

	log.Printf("[SUPER SOAR AGENT] Listening on %s (allowlist enforced, HMAC required)", listenAddr)
	if err := http.ListenAndServe(listenAddr, nil); err != nil {
		log.Fatalf("Agent fatal error: %v", err)
	}
}
