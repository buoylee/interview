// Go 生產級日誌範例 —— 把 logging/ 六章紀律組裝在一個 gin 服務裡。
//
// 端點:GET /users/:id
//   id <= 0  → 參數非法,記 INFO(正常業務,不是 ERROR),回 400
//   id == 13 → 查無此人,記 INFO(正常業務),回 404
//   id == 99 → 模擬下游故障,repo 用 %w 包裝往上回傳 → 頂層記一次完整鏈,回 500
//   其他     → 成功,記 INFO,回 200
//
// 跑法:  go run .        然後  curl -H 'X-Request-ID: demo-1' localhost:8080/users/42
// 驗證:  go test -v
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

// --- 03:request_id 隨 context 走,自訂 handler 把它注入每一筆 record ---
type ridKey struct{}

type contextHandler struct{ slog.Handler }

func (h contextHandler) Handle(ctx context.Context, r slog.Record) error {
	if rid, ok := ctx.Value(ridKey{}).(string); ok {
		r.AddAttrs(slog.String("request_id", rid))
	}
	return h.Handler.Handle(ctx, r)
}

var logger *slog.Logger

// 05:啟動時設好全域 leveled JSON handler(寫 stdout,12-factor)
func initLogger() {
	base := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})
	logger = slog.New(contextHandler{base})
	slog.SetDefault(logger)
}

func genID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// --- 04:資料層只「包裝 + 往上回傳」,不在這裡記 log ---
var errUserNotFound = errors.New("user not found") // 可預期業務狀況 → 哨兵錯誤

func fetchUser(ctx context.Context, uid int) (map[string]any, error) {
	if uid == 99 {
		// 模擬下游/DB 故障:用 %w 包裝加上下文,保留 cause chain,但不在這裡記
		downstream := errors.New("connection reset by peer")
		return nil, fmt.Errorf("load user failed, uid=%d: %w", uid, downstream)
	}
	if uid == 13 {
		return nil, errUserNotFound
	}
	return map[string]any{"id": uid, "name": fmt.Sprintf("user%d", uid)}, nil
}

// --- 02/03:請求邊界中介層 —— 設定 request_id、記進出 ---
func loggingMiddleware(c *gin.Context) {
	rid := c.GetHeader("X-Request-ID")
	if rid == "" {
		rid = genID()
	}
	ctx := context.WithValue(c.Request.Context(), ridKey{}, rid)
	c.Request = c.Request.WithContext(ctx)
	c.Header("X-Request-ID", rid)

	start := time.Now()
	logger.InfoContext(ctx, "request started", "method", c.Request.Method, "path", c.FullPath())
	c.Next() // 跑後續 handler
	logger.InfoContext(ctx, "request finished",
		"status", c.Writer.Status(), "latency_ms", time.Since(start).Milliseconds())
}

// --- 端點 ---
func getUser(c *gin.Context) {
	ctx := c.Request.Context()
	uid, err := strconv.Atoi(c.Param("id"))
	if err != nil || uid <= 0 {
		logger.InfoContext(ctx, "invalid user id, rejecting", "raw", c.Param("id")) // 01:業務,INFO
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid id"})
		return
	}

	user, err := fetchUser(ctx, uid)
	if err != nil {
		if errors.Is(err, errUserNotFound) { // errors.Is 穿透 %w 鏈比對哨兵
			logger.InfoContext(ctx, "user not found", "uid", uid) // 01:業務,INFO
			c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
			return
		}
		// 04:不可預期的失敗 → 在頂層記一次,err 帶完整 %w 鏈
		logger.ErrorContext(ctx, "request failed", "uid", uid, "err", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal"})
		return
	}

	logger.InfoContext(ctx, "user fetched", "uid", uid) // 02:業務里程碑
	c.JSON(http.StatusOK, user)
}

func newRouter() *gin.Engine {
	// 05:用 gin.New() 而非 gin.Default() —— 不要 gin 自帶的文字 logger,改用我們的 slog
	r := gin.New()
	r.Use(gin.Recovery()) // 保留 panic 復原
	r.Use(loggingMiddleware)
	r.GET("/users/:id", getUser)
	return r
}

func main() {
	initLogger()
	gin.SetMode(gin.ReleaseMode)
	r := newRouter()
	logger.Info("server starting", "addr", ":8080")
	if err := r.Run(":8080"); err != nil {
		logger.Error("server exited", "err", err)
		os.Exit(1)
	}
}
