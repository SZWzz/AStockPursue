.PHONY: run test lint clean

run:
	go run ./cmd/server

test:
	go test ./... -v -count=1

lint:
	golangci-lint run ./...

vet:
	go vet ./...

build:
	go build -o bin/server ./cmd/server

clean:
	rm -rf bin/
