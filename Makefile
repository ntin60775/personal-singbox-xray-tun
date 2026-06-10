.PHONY: all build build-release test lint clean

all: build

build:
	cd backend && CGO_ENABLED=0 go build -ldflags="-s -w" -o ../subvostd ./cmd/subvostd

build-release:
	cd backend && GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -ldflags="-s -w" -o ../dist/subvostd ./cmd/subvostd

test:
	cd backend && go test ./...
	@echo ""
	@echo "--- Python tests ---"
	cd . && python3 -m unittest discover tests/ -q

lint:
	cd backend && go vet ./...
	cd . && bash -n libexec/*.sh lib/*.sh *.sh 2>/dev/null || true

clean:
	rm -f subvostd
	rm -rf dist/

serve: build
	./subvostd --mode serve

start: build
	sudo ./subvostd --mode start

stop:
	sudo ./subvostd --mode stop

diag:
	./subvostd --mode diag
