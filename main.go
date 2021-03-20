package main

import (
    "flag"
    "fmt"
	"encoding/json"
)

type Identifier struct {
    Name string `json:"name"`
    Description string `json:"description"`
    Regex string `json:"regex"`
}

type Book struct {
    Name string `json:"name"`
    Description string `json:"description"`
}


func main() {
    textPtr := flag.String("text", "", "Text to parse.")
    flag.Parse()

    fmt.Printf("textPtr: %s, metricPtr: %s, uniquePtr: %t\n", *textPtr)

    data := Identifier{Name: "Ethereum", Description: "Yes", Regex: "*"}
    //book := Book{Name: "Learning Concurrency in Python", Description: "yes"}
    

    byteArray, err := json.Marshal(data)
    if err != nil{
        fmt.Println(err)
    }

    fmt.Println(string(byteArray))
}