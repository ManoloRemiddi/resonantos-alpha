// Package services contains an implementation of the grpc MangleServer interface.
package service

import (
	"bytes"
	"compress/gzip"
	"context"
	"io"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/google/mangle/analysis"
	"github.com/google/mangle/ast"
	"github.com/google/mangle/engine"
	"github.com/google/mangle/factstore"
	"github.com/google/mangle/parse"

	pb "github.com/burakemir/mangle-service/proto"
)

var programInfo *analysis.ProgramInfo

func copyDecl(decls map[ast.PredicateSym]*ast.Decl) map[ast.PredicateSym]ast.Decl {
	m := make(map[ast.PredicateSym]ast.Decl, len(decls))
	for k, v := range decls {
		m[k] = *v
	}
	return m
}

type MangleService struct {
	pb.UnimplementedMangleServer
	store       factstore.FactStore
	programInfo *analysis.ProgramInfo
	lock        sync.Mutex
	evalFn      func(store factstore.FactStore) (engine.Stats, error)
}

func New(dbPath string) (*MangleService, error) {
	var store factstore.FactStore

	if dbPath == "" {
		store = factstore.NewSimpleInMemoryStore()
	} else {
		// This reads the entire contents into memory.
		// The fact that it is gzipped may make this more
		// bearable, but if you have a large DB or small memory
		// then you may want to do things differently.
		dbBytes, err := os.ReadFile(dbPath)
		if err != nil {
			return nil, err
		}
		s, err := factstore.NewSimpleColumnStoreFromGzipBytes(dbBytes)
		if err != nil {
			return nil, err
		}
		store = factstore.NewMergedStore([]factstore.ReadOnlyFactStore{s}, factstore.NewIndexedInMemoryStore())
	}
	return &MangleService{store: store, lock: sync.Mutex{}, programInfo: programInfo}, nil
}

// This should only be called once.
func (m *MangleService) PersistCallback(dbPath string) func() {
	return func() {
		m.lock.Lock()
		defer m.lock.Unlock()
		var start = time.Now()
		var b bytes.Buffer
		w := gzip.NewWriter(&b)
		sc := factstore.SimpleColumn{} // non-deterministic
		if err := sc.WriteTo(m.store, w); err != nil {
			log.Fatal(err)
		}
		if err := w.Close(); err != nil {
			log.Fatal(err)
		}
		if err := os.WriteFile(dbPath, b.Bytes(), 0644); err != nil {
			log.Fatal(err)
		}
		log.Printf("wrote db at %s (%s)", dbPath, time.Now().Sub(start))
	}
}

// Parses, analyzes and evaluates source, using current store.
func (m *MangleService) UpdateFromSource(reader io.Reader) error {
	u, err := parse.Unit(reader)
	if err != nil {
		return err
	}
	info, err := analysis.Analyze([]parse.SourceUnit{u}, nil)
	if err != nil {
		return err
	}
	programInfo = info
	strata, predToStratum, err := analysis.Stratify(analysis.Program{
		EdbPredicates: programInfo.EdbPredicates,
		IdbPredicates: programInfo.IdbPredicates,
		Rules:         programInfo.Rules,
	})
	if err != nil {
		return err
	}
	m.evalFn = func(store factstore.FactStore) (engine.Stats, error) {
		return engine.EvalStratifiedProgramWithStats(programInfo, strata, predToStratum, store)
	}
	stats, err := m.evalFn(m.store)
	if err != nil {
		return err
	}
	log.Printf("service.go:UpdateFromSource: initial eval finished. \nstats: %v\nnum facts:%d",
		stats, m.store.EstimateFactCount())
	return nil
}

func (m *MangleService) Query(req *pb.QueryRequest, stream pb.Mangle_QueryServer) error {
	var store = m.store
	if program := req.GetProgram(); program != "" {
		u, err := parse.Unit(strings.NewReader(program))
		if err != nil {
			return err
		}
		programInfo, err := analysis.Analyze([]parse.SourceUnit{u}, copyDecl(programInfo.Decls))
		if err != nil {
			return err
		}
		store = factstore.NewTeeingStore(store)
		stats, err := engine.EvalProgramWithStats(programInfo, store)
		if err != nil {
			return err
		}
		log.Printf("service.go:Query evaluation of request program finished. stats: %v\n", stats)
		log.Printf("service.go:Query store predicates: %s\n", store.ListPredicates())
	}

	query := req.GetQuery()
	u, err := parse.Atom(query)
	if err != nil {
		log.Printf("service.go:Query parse %q (query) failed: %v\n", query, err)
		return err
	}

	log.Printf("querying store with query %v", u)
	err = store.GetFacts(u, func(a ast.Atom) error {
		answer := &pb.QueryAnswer{
			Answer: a.String(),
		}
		if err := stream.Send(answer); err != nil {
			log.Printf("service.go: got send err: %v", err)
			return err
		}
		return nil
	})
	if err != nil {
		return err
	}
	return nil
}

func (m *MangleService) Update(ctx context.Context, req *pb.UpdateRequest) (*pb.UpdateAnswer, error) {
	u, err := parse.Unit(strings.NewReader(req.GetProgram()))
	if err != nil {
		return nil, err
	}
	//programInfo, err := analysis.Analyze([]parse.SourceUnit{u}, copyDecl(programInfo.Decls))
	if err != nil {
		return nil, err
	}
	info, err := analysis.Analyze([]parse.SourceUnit{u}, nil)
	if err != nil {
		return nil, err
	}
	programInfo = info
	strata, predToStratum, err := analysis.Stratify(analysis.Program{
		EdbPredicates: programInfo.EdbPredicates,
		IdbPredicates: programInfo.IdbPredicates,
		Rules:         programInfo.Rules,
	})
	if err != nil {
		return nil, err
	}

	updates := factstore.NewSimpleInMemoryStore()
	merging := factstore.NewMergedStore([]factstore.FactStore{m.store}, updates)
	stats, err := engine.EvalStratifiedProgramWithStats(programInfo, strata, predToStratum, merging)
	if err != nil {
		return nil, err
	}

	var updatedPreds []string
	for _, sym := range updates.ListPredicates() {
		updatedPreds = append(updatedPreds, sym.Symbol)
	}

	answer := &pb.UpdateAnswer{UpdatedPredicates: updatedPreds}
	log.Printf("Updated, stats: %v\n updated preds: %v", stats, answer)
	m.lock.Lock()
	defer m.lock.Unlock()
	m.store.Merge(updates)
	return answer, nil
}
