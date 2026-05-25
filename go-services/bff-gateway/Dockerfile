FROM docker.m.daocloud.io/library/golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
RUN go build -o /out/bff-gateway ./cmd/bff-gateway

FROM docker.m.daocloud.io/library/alpine:3.20
RUN adduser -D -H appuser
USER appuser
COPY --from=build /out/bff-gateway /usr/local/bin/bff-gateway
EXPOSE 8091
ENTRYPOINT ["bff-gateway"]
