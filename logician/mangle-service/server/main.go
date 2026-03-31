package main

import (
	"context"
	"flag"
	"io"
	"log"
	"net"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	pb "github.com/burakemir/mangle-service/proto"
	"github.com/burakemir/mangle-service/service"
	"google.golang.org/grpc"
)

var (
	oneMin, _ = time.ParseDuration("60s")
	mode      = flag.String("mode", "tcp", "whether grpc or socket")
	sockAddr  = flag.String("sock-addr", "/tmp/mangle.sock", "socket address to use")
	source    = flag.String("source", "", "path to source to evaluate")
	db        = flag.String("db", "", "path to a db, in 'gzipped simplecolumn' format. An empty file works.")

	persist         = flag.Bool("persist", false, "if true, persists in-memory state.")
	persistInterval = flag.Duration("persist-interval", oneMin, "interval at which to persist memory state")
)

func readSource() io.Reader {
	sourceBytes, err := os.ReadFile(*source)
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("read source from %q", *source)
	return strings.NewReader(string(sourceBytes))
}

func listenAndServe(server *grpc.Server) {
	var (
		listener net.Listener
		err      error
	)

	switch *mode {
	case "tcp":
		{
			port := ":8080"
			log.Println("listen and serving on ", port)
			listener, err = net.Listen("tcp", port)
		}
	case "unix":
		{
			log.Println("listen and serving on ", *sockAddr)

			if removeErr := os.RemoveAll(*sockAddr); removeErr != nil {
				log.Fatal(removeErr)
			}

			listener, err = net.Listen("unix", *sockAddr)
		}
	default:
		log.Fatalf("unknown --mode: %q", *mode)
	}

	if err != nil {
		panic(err)
	}

	if err := server.Serve(listener); err != nil {
		panic(err)
	}
}

type persistor struct {
	ticker          *time.Ticker
	requestShutdown chan struct{}
	done            chan struct{}
}

func setUpPersistor(interval time.Duration, cb func()) *persistor {
	ticker := time.NewTicker(interval)
	requestShutdown := make(chan struct{})
	done := make(chan struct{})
	go func() {
		for {
			select {
			case <-requestShutdown:
				cb()
				done <- struct{}{}
				return
			case <-ticker.C:
				cb()
			}
		}
	}()
	return &persistor{ticker, requestShutdown, done}
}

func main() {
	flag.Parse()

	mangleService, err := service.New(*db)
	if err != nil {
		log.Fatal(err)
	}

	if *source != "" {
		if err := mangleService.UpdateFromSource(readSource()); err != nil {
			log.Fatal(err)
		}
		log.Printf("updated db.")
	} else {
		log.Println("no --source given.")
	}

	var persistor *persistor
	if *persist {
		if *db == "" {
			log.Fatal("Cannot --persist without --db path.")
		}
		persistor = setUpPersistor(*persistInterval, mangleService.PersistCallback(*db))
	}

	server := grpc.NewServer()
	pb.RegisterMangleServer(server, mangleService)

	basectx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	go listenAndServe(server)
	<-basectx.Done()
	log.Println("shutting down")
	if persistor != nil {
		persistor.ticker.Stop()
		persistor.requestShutdown <- struct{}{}
		<-persistor.done
	}
	log.Println("bye")
	server.GracefulStop()
}
