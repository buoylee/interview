package main

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

// 驗證:打四種請求,slog 的結構化日誌會輸出到 stdout。
//   go test -v
func TestEndpoints(t *testing.T) {
	initLogger()
	gin.SetMode(gin.TestMode)
	r := newRouter()

	cases := []struct {
		uid  string
		want int
	}{
		{"42", http.StatusOK},
		{"0", http.StatusBadRequest},
		{"13", http.StatusNotFound},
		{"99", http.StatusInternalServerError},
	}
	for _, tc := range cases {
		req := httptest.NewRequest(http.MethodGet, "/users/"+tc.uid, nil)
		req.Header.Set("X-Request-ID", "req-"+tc.uid)
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != tc.want {
			t.Errorf("uid=%s: got status %d, want %d", tc.uid, w.Code, tc.want)
		}
	}
}
