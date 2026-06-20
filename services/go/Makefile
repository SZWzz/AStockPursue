.PHONY: run test lint vet build gen-proto clean

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

gen-proto:
	cd ../proto && buf generate

clean:
	rm -rf bin/
