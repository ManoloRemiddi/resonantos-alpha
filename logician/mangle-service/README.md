Demo grpc service for trying out Mangle deductive database.

Mangle is an extension of Datalog.
The repo is here: https://github.com/google/mangle

## Building

```go
go get ./...
go build ./...
```

## Run the Server

This starts the gprc server, with a tiny database.

```
go run ./server --source=example/demo.mg
```

## Run the Client

This queries the gprc server, with a recursive query.

```go
go run ./client
go run ./client --query="reachable(X, /d)"
```

### Alternatively: use grpcurl

```
grpcurl -plaintext -use-reflection=false -proto proto/mangle.proto \
  -d '{"query": "edge(/a, X)" }' localhost:8080 mangle.Mangle.Query

```

`grpcurl` can be obtained like so:

```
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
```


## Regenerate the proto files

```shell
cd proto
protoc --go_out=. --go_opt=paths=source_relative \
  --go-grpc_out=. --go-grpc_opt=paths=source_relative mangle.proto
```


# Persistence demo

Reminder: do not use this as a serious DB.
The following is a demo deductive databse.

## Create an empty db file

```
echo "0" | gzip - > /tmp/foo.mangle.db.gz
```

## Start services with DB path

The following will load your (empty) DB and evaluate your program.
Our demo program is the same, it contains only definitions of edges.
```
go run server/main.go --db=/tmp/foo.mangle.db.gz --source=example/demo.mg --persist=true
```

## Add more edges

The client code only does querying, so we use `grpcurl` to send updates.

```
grpcurl -plaintext -use-reflection=false -proto proto/mangle.proto \
  -d '{"program": "edge(/d, /e). edge(/e, /f)." }' localhost:8080 mangle.Mangle.Update
```

When we run the query again, we find that our service now returns additional reachable nodes.

For every query, the service implementation does the computation of reachable nodes.
If we know these queries in advance, we could also send an update that performs the computation.
