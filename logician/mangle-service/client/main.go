package main

import (
	"context"
	"flag"
	"io"
	"log"
	"net"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/burakemir/mangle-service/proto"
)

var (
	mode     = flag.String("mode", "tcp", "whether grpc over tcp or unix (socket) - pick one.")
	sockAddr = flag.String("sock-addr", "/tmp/mangle.sock", "socket address to use")
	query    = flag.String("query", "reachable(/a, X)", "query to send")
)

// Sample recursive query.
var program = `
reachable(X, Y) :- edge(X, Y).
reachable(X, Z) :- edge(X, Y), reachable(Y, Z).
`

func sockDialer(addr string, _ time.Duration) (net.Conn, error) {
	return net.Dial("unix", *sockAddr)
}

func main() {
	flag.Parse()
	var (
		conn *grpc.ClientConn
		err  error
	)

	switch *mode {
	case "tcp":
		{
			conn, err = grpc.Dial("localhost:8080", grpc.WithTransportCredentials(insecure.NewCredentials()))
		}
	case "unix":
		{
			conn, err = grpc.Dial(*sockAddr, grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithDialer(sockDialer))
		}
	}

	if err != nil {
		panic(err)
	}
	defer conn.Close()

	client := pb.NewMangleClient(conn)
	stream, err := client.Query(context.Background(), &pb.QueryRequest{Query: *query, Program: program})
	if err != nil {
		panic(err)
	}
	log.Printf("[query %q]", *query)
	var answer *pb.QueryAnswer
	n := 0
	for {
		answer, err = stream.Recv()
		if err != nil {
			break
		}
		n++
		log.Printf("got answer %q", answer.GetAnswer())
	}
	if err != io.EOF {
		log.Printf("got err %v", err)
	}
	log.Printf("[got %d answers]", n)
}
