package com.interview.mysqlescdc.consumer.rebuild;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import com.interview.mysqlescdc.consumer.canal.*;
import com.interview.mysqlescdc.consumer.projection.*;
import com.interview.mysqlescdc.consumer.sink.*;
import com.interview.mysqlescdc.consumer.source.*;

@Component
public final class KafkaShadowReplayService implements ShadowReplayService {
    private final String bootstrap; private final JdbcClient jdbc; private final CanalRevisionParser parser;
    private final SourceSnapshotRepository source; private final SearchDocumentProjector projector; private final ElasticsearchGateway sink;
    private final AtomicReference<ShadowReplayStatus> status = new AtomicReference<>(new ShadowReplayStatus(null, ShadowReplayState.IDLE, Map.of(), null));
    private volatile KafkaConsumer<String,String> consumer; private volatile Thread worker;
    public KafkaShadowReplayService(@Value("${spring.kafka.bootstrap-servers}") String bootstrap, JdbcClient jdbc,
            CanalRevisionParser parser, SourceSnapshotRepository source, SearchDocumentProjector projector, ElasticsearchGateway sink) {
        this.bootstrap=bootstrap; this.jdbc=jdbc; this.parser=parser; this.source=source; this.projector=projector; this.sink=sink;
    }
    @Override public synchronized ShadowReplayStatus start(ShadowReplayRequest r) {
        Objects.requireNonNull(r); if (status.get().state()==ShadowReplayState.RUNNING) throw new IllegalStateException("shadow replay already running");
        validate(r); var initial = new ShadowReplayStatus(r.runId(),ShadowReplayState.RUNNING,Map.copyOf(r.offsets()),null); status.set(initial);
        worker=Thread.ofVirtual().name("shadow-replay-"+r.runId()).start(() -> run(r)); return initial;
    }
    private void validate(ShadowReplayRequest r) {
        if(r.runId()==null||r.topic()==null||r.topic().isBlank()||r.offsets()==null||r.offsets().size()!=3||
                !r.offsets().keySet().equals(Set.of(0,1,2))||r.offsets().values().stream().anyMatch(v->v==null||v<0)) throw new IllegalArgumentException("exact three non-negative offsets required");
        ElasticsearchTargets.requireSafe(r.target());
    }
    private void run(ShadowReplayRequest r) {
        try (var c = createConsumer()) { consumer=c; var partitions=r.offsets().keySet().stream().sorted().map(p->new TopicPartition(r.topic(),p)).toList();
            c.assign(partitions); var beginnings=c.beginningOffsets(partitions); var ends=c.endOffsets(partitions);
            for(var tp:partitions){long wanted=r.offsets().get(tp.partition()); if(wanted<beginnings.get(tp)||wanted>ends.get(tp))throw new IllegalStateException("required offset unavailable"); c.seek(tp,wanted);}
            while(!Thread.currentThread().isInterrupted()) { var records=c.poll(Duration.ofMillis(200));
                for(var record:records){ settle(r,record); advance(r,record.partition(),record.offset()+1); }
                if(done(c,partitions,ends)){status.updateAndGet(s->new ShadowReplayStatus(s.runId(),ShadowReplayState.COMPLETED,s.nextOffsets(),null));return;}
            }
        } catch (org.apache.kafka.common.errors.WakeupException e) { status.updateAndGet(s->new ShadowReplayStatus(s.runId(),ShadowReplayState.STOPPED,s.nextOffsets(),null)); }
          catch (Exception e) { status.updateAndGet(s->new ShadowReplayStatus(s.runId(),ShadowReplayState.FAILED,s.nextOffsets(),e.getClass().getSimpleName())); }
        finally {consumer=null;}
    }
    private void settle(ShadowReplayRequest r, ConsumerRecord<String,String> record) {
        var signals=parser.parse(record.value()); if(signals.isEmpty()) return;
        var byId=new TreeMap<Long,RevisionSignal>(); for(var s:signals)byId.merge(s.productId(),s,(a,b)->a.eventRevision()>=b.eventRevision()?a:b);
        var docs=new ArrayList<SearchDocument>(); for(var signal:byId.values()) { var snapshot=source.load(signal.productId()).orElseThrow(()->new IllegalStateException("missing source")); if(snapshot.revision()<signal.eventRevision())throw new IllegalStateException("source behind signal"); docs.add(projector.project(snapshot)); }
        var result=sink.write(r.target(),docs); if(result.items().size()!=docs.size()||result.items().stream().anyMatch(i->i.outcome()!=BulkOutcome.APPLIED&&i.outcome()!=BulkOutcome.STALE))throw new IllegalStateException("shadow poison");
    }
    private void advance(ShadowReplayRequest r,int partition,long next) { jdbc.sql("INSERT INTO rebuild_partition_offset(run_id,phase,topic_name,partition_id,next_offset) VALUES(UUID_TO_BIN(:run),'SHADOW',:topic,:partition,:next) ON DUPLICATE KEY UPDATE next_offset=GREATEST(next_offset,VALUES(next_offset))")
            .param("run",r.runId().toString()).param("topic",r.topic()).param("partition",partition).param("next",next).update();
        status.updateAndGet(s->{var m=new TreeMap<>(s.nextOffsets());m.merge(partition,next,Math::max);return new ShadowReplayStatus(s.runId(),s.state(),Map.copyOf(m),s.failureClass());}); }
    private static boolean done(KafkaConsumer<String,String> c,List<TopicPartition> ps,Map<TopicPartition,Long> ends){return ps.stream().allMatch(p->c.position(p)>=ends.get(p));}
    private KafkaConsumer<String,String> createConsumer(){var p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");p.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG,"read_committed");p.put(ConsumerConfig.GROUP_ID_CONFIG,"shadow-"+UUID.randomUUID());return new KafkaConsumer<>(p);}
    @Override public ShadowReplayStatus status(){return status.get();}
    @Override public synchronized ShadowReplayStatus stop(){var c=consumer;if(c!=null)c.wakeup();var w=worker;if(w!=null)try{w.join(Duration.ofSeconds(5));}catch(InterruptedException e){Thread.currentThread().interrupt();}if(w!=null&&w.isAlive())throw new IllegalStateException("shadow stop timeout");return status.get();}
}
