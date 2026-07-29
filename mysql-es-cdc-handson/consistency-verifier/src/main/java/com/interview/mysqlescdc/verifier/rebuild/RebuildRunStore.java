package com.interview.mysqlescdc.verifier.rebuild;
import java.util.List;
import java.util.UUID;
public interface RebuildRunStore{void create(RebuildRequest request);void transition(UUID runId,String expected,String next);void fail(UUID runId,Throwable failure);RebuildStatus get(UUID runId);default List<UUID> nonterminal(){return List.of();}}
