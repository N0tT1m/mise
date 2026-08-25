// Mise :: API skeleton.
//
// Every endpoint is a stub. The route table is the contract from the spec;
// filling these in is phases 3 through 5.
//
// One rule this file exists to enforce: the app READS. Parsing, extraction and
// resolution all belong to the offline pipeline. Nothing in a request path
// should ever import them.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"
)

func main() {
	// Fail closed. A missing connection string is a startup error, never a default.
	if os.Getenv("MISE_DATABASE_URL") == "" {
		log.Fatal("MISE_DATABASE_URL is not set. Refusing to start rather than guessing.")
	}

	addr := os.Getenv("MISE_ADDR")
	if addr == "" {
		addr = ":8000"
	}

	srv := &http.Server{
		Addr:              addr,
		Handler:           routes(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	// Stop accepting on SIGINT/SIGTERM, then let in-flight requests drain.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := srv.Shutdown(shutdown); err != nil {
			log.Printf("shutdown: %v", err)
		}
	}()

	log.Printf("mise api listening on %s", addr)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("serve: %v", err)
	}
}

func routes() http.Handler {
	mux := http.NewServeMux()

	// --- recipes -----------------------------------------------------------

	// Fused keyword + semantic search, with filters.
	mux.HandleFunc("GET /recipes/search", notBuiltYet("phase 4"))

	// One recipe, with its resolved ingredient lines.
	mux.HandleFunc("GET /recipes/{id}", requireID("id", notBuiltYet("phase 4")))

	// --- pantry ------------------------------------------------------------

	// Current pantry contents.
	mux.HandleFunc("GET /pantry", notBuiltYet("phase 3"))

	// Add or update a pantry item.
	mux.HandleFunc("POST /pantry", notBuiltYet("phase 3"))

	// Remove a pantry item.
	mux.HandleFunc("DELETE /pantry/{ingredientId}", requireID("ingredientId", notBuiltYet("phase 3")))

	// --- matching ----------------------------------------------------------

	// Recipes fully covered by the pantry.
	mux.HandleFunc("GET /match/cookable", notBuiltYet("phase 3"))

	// Recipes within N missing items, ranked by count then difficulty.
	mux.HandleFunc("GET /match/nearly", func(w http.ResponseWriter, r *http.Request) {
		if _, ok := intQuery(w, r, "missing", 2); !ok {
			return
		}
		notBuiltYet("phase 3")(w, r)
	})

	// --- generation --------------------------------------------------------

	// Constraints in, grounded recipe out.
	mux.HandleFunc("POST /generate", notBuiltYet("phase 5"))

	// --- feedback and review -----------------------------------------------

	// Log that you cooked it, with a rating.
	mux.HandleFunc("POST /cooked", notBuiltYet("phase 3"))

	// Highest-impact open review item.
	mux.HandleFunc("GET /review/next", notBuiltYet("phase 2"))

	// Accept, correct, or reject a proposal.
	mux.HandleFunc("POST /review/{id}", requireID("id", notBuiltYet("phase 2")))

	// --- health ------------------------------------------------------------

	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})

	return mux
}

// notBuiltYet is the placeholder every route currently answers with. The phase
// tells you which section of the spec fills it in.
func notBuiltYet(phase string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusNotImplemented, map[string]string{
			"error": "not implemented",
			"phase": phase,
		})
	}
}

// requireID enforces the numeric path constraints the route table declares, so
// /recipes/abc is a 400 here rather than a database error later.
func requireID(name string, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		raw := r.PathValue(name)
		if _, err := strconv.ParseInt(raw, 10, 64); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{
				"error": name + " must be an integer",
			})
			return
		}
		next(w, r)
	}
}

// intQuery reads an optional integer query parameter, writing a 400 and
// reporting false if it is present but unparseable.
func intQuery(w http.ResponseWriter, r *http.Request, name string, fallback int) (int, bool) {
	raw := r.URL.Query().Get(name)
	if raw == "" {
		return fallback, true
	}
	n, err := strconv.Atoi(raw)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error": name + " must be an integer",
		})
		return 0, false
	}
	return n, true
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(body); err != nil {
		log.Printf("write response: %v", err)
	}
}
