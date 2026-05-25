FROM docker.m.daocloud.io/library/golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
RUN go build -o /out/market-read-service ./cmd/market-read-service

FROM docker.m.daocloud.io/library/alpine:3.20
RUN adduser -D -H appuser
USER appuser
COPY --from=build /out/market-read-service /usr/local/bin/market-read-service
EXPOSE 8092
ENTRYPOINT ["market-read-service"]
