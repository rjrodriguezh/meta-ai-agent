FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o ai-service .

FROM alpine:latest
RUN apk add --no-cache wget
WORKDIR /app
COPY --from=builder /app/ai-service .

EXPOSE 8081
CMD ["./ai-service"]
