FROM golang:1.22-alpine AS builder

WORKDIR /app
# Copiar todo el código primero para que go mod tidy pueda resolver imports
COPY . .
# Generar go.sum y descargar dependencias
RUN go mod tidy && go build -o activities-service .

FROM alpine:latest
RUN apk add --no-cache wget
WORKDIR /app
COPY --from=builder /app/activities-service .

EXPOSE 8084
CMD ["./activities-service"]
