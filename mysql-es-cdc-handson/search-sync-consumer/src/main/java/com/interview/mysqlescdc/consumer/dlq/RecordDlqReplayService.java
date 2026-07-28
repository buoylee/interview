package com.interview.mysqlescdc.consumer.dlq;

import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import com.interview.mysqlescdc.consumer.canal.*;
import com.interview.mysqlescdc.consumer.projection.*;
import com.interview.mysqlescdc.consumer.sink.*;
import com.interview.mysqlescdc.consumer.source.*;

@Service
public class RecordDlqReplayService {
    private final RecordDlqStore store; private final CanalRevisionParser parser;
    private final SourceSnapshotRepository source; private final SearchDocumentProjector projector;
    private final ElasticsearchGateway elasticsearch; private final String targetAlias;
    public RecordDlqReplayService(RecordDlqStore store, CanalRevisionParser parser,
            SourceSnapshotRepository source, SearchDocumentProjector projector,
            ElasticsearchGateway elasticsearch,
            @Value("${pipeline.target-alias:products_write}") String targetAlias) {
        this.store=store; this.parser=parser; this.source=source; this.projector=projector;
        this.elasticsearch=elasticsearch; this.targetAlias=targetAlias;
    }
    public RecordReplayResult replay(String recordId) {
        var found=store.findPending(recordId);
        if(found.isEmpty()) return RecordReplayResult.notFound(recordId);
        RecordDlqRecord pending=found.get();
        List<RevisionSignal> parsed;
        try { parsed=parser.parse(pending.rawPayload()); } catch(RuntimeException failure) { return remain(pending); }
        LinkedHashSet<Long> ids=new LinkedHashSet<>(); parsed.forEach(s -> ids.add(s.productId()));
        List<SearchDocument> docs=new ArrayList<>();
        try {
            for(long id: ids) { var snapshot=source.load(id); if(snapshot.isEmpty()) return remain(pending); docs.add(projector.project(snapshot.get())); }
        } catch(RuntimeException failure) { return remain(pending); }
        BulkWriteResult result;
        try { result=elasticsearch.write(targetAlias, docs); } catch(BulkTransportException|BulkProtocolException failure) { return remain(pending); }
        if(result.items().size()!=docs.size()) return remain(pending);
        List<BulkOutcome> outcomes=new ArrayList<>();
        for(int i=0;i<docs.size();i++) {
            var d=docs.get(i); var item=result.items().get(i);
            if(item.productId()!=d.productId() || item.revision()!=d.sourceRevision()) return remain(pending);
            outcomes.add(item.outcome());
            if(item.outcome()!=BulkOutcome.APPLIED && item.outcome()!=BulkOutcome.STALE) return remain(pending);
        }
        store.resolve(recordId);
        return new RecordReplayResult(recordId,outcomes,true,ReplayStatus.RESOLVED);
    }
    private RecordReplayResult remain(RecordDlqRecord r) {
        store.publish(RecordDlqRecord.newPending(r.recordId(),r.topic(),r.partition(),r.offset(),
                r.rawKey(),r.rawPayload(),r.failureClass(),r.lastError()));
        return new RecordReplayResult(r.recordId(),List.of(),false,ReplayStatus.PENDING);
    }
}
