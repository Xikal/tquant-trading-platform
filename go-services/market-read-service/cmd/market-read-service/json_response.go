package main

import (
	"encoding/json"
	"net/http"
)

func writeJSONPayload(w http.ResponseWriter, payload any) {
	_ = json.NewEncoder(w).Encode(payload)
}
