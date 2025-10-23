package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"syscall"
	"time"

	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"

	_ "github.com/mattn/go-sqlite3"
)

func eventHandler(evt any) {
	switch v := evt.(type) {
	case *events.Message:
		fmt.Println("Received a message!", v.Message.GetConversation())
	}
}

func main() {
	dbLog := waLog.Stdout("Database", "DEBUG", true)
	ctx := context.Background()
	container, err := sqlstore.New(ctx, "sqlite3", "file:examplestore.db?_foreign_keys=on", dbLog)
	if err != nil {
		panic(err)
	}
	deviceStore, err := container.GetFirstDevice(ctx)
	if err != nil {
		panic(err)
	}
	clientLog := waLog.Stdout("Client", "DEBUG", true)
	client := whatsmeow.NewClient(deviceStore, clientLog)
	client.AddEventHandler(eventHandler)

	if err := client.Connect(); err != nil {
		log.Printf("Error connecting whatsmeow client: %v", err)
	}

	srv := &http.Server{
		Addr: ":4005",
	}

	http.HandleFunc("/send-message", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		type reqBody struct {
			Phnnumber string `json:"phnnumber"`
			Content   string `json:"content"`
		}
		var rb reqBody
		if err := json.NewDecoder(r.Body).Decode(&rb); err != nil {
			http.Error(w, "invalid json body", http.StatusBadRequest)
			return
		}
		phone := normalizePhone(rb.Phnnumber)
		if phone == "" || strings.TrimSpace(rb.Content) == "" {
			http.Error(w, "phnnumber and content are required", http.StatusBadRequest)
			return
		}
		if err := SendMessage(client, phone, rb.Content); err != nil {
			log.Printf("SendMessage error: %v", err)
			http.Error(w, fmt.Sprintf("failed to send message: %v", err), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]any{"success": true})
	})

	go func() {
		log.Printf("Starting HTTP server on %s", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP server ListenAndServe: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	log.Println("Shutting down server...")
	ctxShut, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctxShut); err != nil {
		log.Fatalf("Server Shutdown Failed:%+v", err)
	}
	client.Disconnect()
}

func SendMessage(client *whatsmeow.Client, phoneNumber string, message string) error {
	jid := types.NewJID(phoneNumber, "s.whatsapp.net")
	_, err := client.SendMessage(context.Background(), jid, &waE2E.Message{
		Conversation:        &message,
		ExtendedTextMessage: &waE2E.ExtendedTextMessage{},
	})
	if err == nil {
		log.Printf("message delivered to -> %s", phoneNumber)
	}

	return err
}

func normalizePhone(raw string) string {
	if raw == "" {
		return ""
	}
	re := regexp.MustCompile(`[^0-9]`)
	cleaned := re.ReplaceAllString(raw, "")
	if len(cleaned) == 10 {
		return "91" + cleaned
	}
	if len(cleaned) >= 11 {
		return cleaned
	}
	return ""
}
