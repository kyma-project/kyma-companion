FROM golang:1.27 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/kyma-docs-search ./cmd/server \
 && echo "app:x:10001:10001::/:/sbin/nologin" > /out/passwd

FROM scratch
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=build /usr/share/zoneinfo /usr/share/zoneinfo
COPY --from=build /out/passwd /etc/passwd
COPY --from=build /out/kyma-docs-search /kyma-docs-search
USER 10001:10001
EXPOSE 8081
ENTRYPOINT ["/kyma-docs-search"]
