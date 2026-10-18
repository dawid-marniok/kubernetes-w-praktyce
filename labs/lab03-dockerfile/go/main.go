package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
)

func main() {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		host, _ := os.Hostname()
		fmt.Fprintf(w, "Hello z Go w kontenerze! host %s, uid %d\n", host, os.Getuid())
	})

	log.Println("Aplikacja słucha na porcie 8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
