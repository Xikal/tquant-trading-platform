FROM docker.m.daocloud.io/library/golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
RUN go build -o /out/scan-worker ./cmd/scan-worker

FROM docker.m.daocloud.io/library/alpine:3.20
RUN adduser -D -H appuser
USER appuser
COPY --from=build /out/scan-worker /usr/local/bin/scan-worker
EXPOSE 8093
ENTRYPOINT ["scan-worker"]
