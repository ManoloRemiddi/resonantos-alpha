package test

import (
	"context"
	"fmt"
	"io"
	"net"
	"slices"
	"strings"
	"testing"

	"github.com/burakemir/mangle-service/service"
	"github.com/google/mangle/ast"
	"github.com/google/mangle/parse"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	pb "github.com/burakemir/mangle-service/proto"
)

const testSource = `
edge(/a, /b).
edge(/b, /c).
edge(/c, /d).`

var testProgram = `
reachable(X, Y) :- edge(X, Y).
reachable(X, Z) :- edge(X, Y), reachable(Y, Z).`

func atom(s string) ast.Atom {
	a, err := parse.Atom("reachable(/a,/b)")
	if err != nil {
		panic(err)
	}
	return a
}

// TestServerClient tests whether request with a program works.
func TestServerClient(t *testing.T) {
	mangleService := service.New()
	reader := strings.NewReader(testSource)
	if err := mangleService.UpdateFromSource(reader); err != nil {
		t.Fatal(err)
	}

	server := grpc.NewServer()
	pb.RegisterMangleServer(server, mangleService)
	go func() {
		port := ":8080"
		listener, err := net.Listen("tcp", port)
		if err != nil {
			panic(err)
		}

		if err := server.Serve(listener); err != nil {
			panic(err)
		}
	}()

	conn, err := grpc.Dial("localhost:8080", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		panic(err)
	}
	client := pb.NewMangleClient(conn)
	var query = "reachable(/a, X)"
	fmt.Printf("testProgram: %q", testProgram)
	stream, err := client.Query(context.Background(), &pb.QueryRequest{Query: query, Program: testProgram})
	if err != nil {
		panic(err)
	}
	var expected = []string{
		atom("reachable(/a,/b)").String(),
		atom("reachable(/a,/c)").String(),
		atom("reachable(/a,/d)").String(),
	}
	var answer *pb.QueryAnswer
	var actual []string
	n := 0
	for {
		answer, err = stream.Recv()
		if err != nil {
			break
		}
		n++
		fmt.Printf("actual answer: %q", answer.GetAnswer())
		actual = append(actual, atom(answer.GetAnswer()).String())
	}
	if err != io.EOF {
		fmt.Printf("got err %v", err)
	}

	for _, a := range expected {
		if !slices.Contains(actual, a) {
			t.Errorf("expected to find %v", a)
		}
	}
}
