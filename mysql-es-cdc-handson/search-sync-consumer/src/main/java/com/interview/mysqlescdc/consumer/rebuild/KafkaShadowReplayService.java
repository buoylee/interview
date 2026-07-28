package com.interview.mysqlescdc.consumer.rebuild;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
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
    private static final int ATTEMPTS=3;
    private final String bootstrap, configuredTopic; private final JdbcClient jdbc; private final CanalRevisionParser parser;
    private final SourceSnapshotRepository source; private final SearchDocumentProjector projector; private final ElasticsearchGateway sink;
    private volatile ShadowReplayRequest active; private volatile ShadowReplayStatus status;
    private final AtomicBoolean stopRequested=new AtomicBoolean(); private volatile KafkaConsumer<String,String> consumer; private volatile Thread worker;
    public KafkaShadowReplayService(@Value("${spring.kafka.bootstrap-servers}") String bootstrap,
            @Value("${pipeline.source-topic:product-search-revisions}") String configuredTopic, JdbcClient jdbc,
            CanalRevisionParser parser, SourceSnapshotRepository source, SearchDocumentProjector projector, ElasticsearchGateway sink) {
        this.bootstrap=bootstrap;this.configuredTopic=configuredTopic;this.jdbc=jdbc;this.parser=parser;this.source=source;this.projector=projector;this.sink=sink;
    }
    @Override public synchronized ShadowReplayStatus start(ShadowReplayRequest request) {
        validate(request); if(active!=null&&status.running()){if(active.equals(request))return status;throw new IllegalStateException(active.runId().equals(request.runId())?"conflicting shadow run":"another shadow run active");}if(worker!=null&&worker.isAlive())throw new IllegalStateException("previous shadow worker terminating");
        active=request;stopRequested.set(false);persistInitial(request);status=snapshot(request,request.offsets(),true,null);
        worker=Thread.ofVirtual().name("shadow-replay-"+request.runId()).start(()->run(request));return status;
    }
    private void validate(ShadowReplayRequest r){Objects.requireNonNull(r);if(r.runId()==null||!configuredTopic.equals(r.topic())||r.offsets()==null||r.offsets().size()!=3||!r.offsets().keySet().equals(Set.of(0,1,2))||r.offsets().values().stream().anyMatch(v->v==null||v<0))throw new IllegalArgumentException("configured topic and exact partitions 0/1/2 required");ElasticsearchTargets.requireSafe(r.target());}
    private void persistInitial(ShadowReplayRequest r){r.offsets().forEach((partition,next)->advance(r,partition,next));}
    private void run(ShadowReplayRequest r){try(var c=createConsumer(r.runId())){consumer=c;if(stopRequested.get())return;var ps=List.of(new TopicPartition(r.topic(),0),new TopicPartition(r.topic(),1),new TopicPartition(r.topic(),2));c.assign(ps);var beginnings=c.beginningOffsets(ps);var ends=c.endOffsets(ps);for(var tp:ps){long wanted=r.offsets().get(tp.partition());if(wanted<beginnings.get(tp))throw new RequiredOffsetExpiredException();if(wanted>ends.get(tp))throw new IllegalArgumentException("required offset ahead of end");c.seek(tp,wanted);}while(!stopRequested.get()){for(var record:c.poll(Duration.ofMillis(200))){settleWithRetry(r,record);advance(r,record.partition(),record.offset()+1);if(stopRequested.get())break;}}}
        catch(org.apache.kafka.common.errors.WakeupException e){if(!stopRequested.get())fail(e);}catch(Exception e){if(!stopRequested.get())fail(e);}finally{consumer=null;if(stopRequested.get()&&status!=null&&status.running())status=snapshot(r,status.nextOffsets(),false,null);}}
    private void settleWithRetry(ShadowReplayRequest r,ConsumerRecord<String,String> record){RuntimeException last=null;for(int attempt=1;attempt<=ATTEMPTS;attempt++){try{settle(r,record);return;}catch(BulkTransportException|BulkProtocolException e){last=e;}catch(RetryableShadowException e){last=e;}if(attempt<ATTEMPTS)try{Thread.sleep(100L*attempt);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new RetryableShadowException(e);}}throw last;}
    private void settle(ShadowReplayRequest r,ConsumerRecord<String,String> record){var signals=parser.parse(record.value());if(signals.isEmpty())return;var byId=new TreeMap<Long,RevisionSignal>();for(var s:signals)byId.merge(s.productId(),s,(a,b)->a.eventRevision()>=b.eventRevision()?a:b);var docs=new ArrayList<SearchDocument>();for(var signal:byId.values()){var snapshot=source.load(signal.productId()).orElseThrow(()->new IllegalStateException("missing source"));if(snapshot.revision()<signal.eventRevision())throw new RetryableShadowException("source behind signal");docs.add(projector.project(snapshot));}var result=sink.write(r.target(),docs);if(result.items().size()!=docs.size())throw new RetryableShadowException("bulk count mismatch");if(result.items().stream().anyMatch(i->i.outcome()==BulkOutcome.PERMANENT_FAILURE))throw new IllegalStateException("shadow poison");if(result.items().stream().anyMatch(i->i.outcome()==BulkOutcome.RETRYABLE_FAILURE))throw new RetryableShadowException("retryable bulk item");}
    private synchronized void advance(ShadowReplayRequest r,int partition,long next){jdbc.sql("INSERT INTO rebuild_partition_offset(run_id,phase,topic_name,partition_id,next_offset) VALUES(UUID_TO_BIN(:run),'SHADOW',:topic,:partition,:next) ON DUPLICATE KEY UPDATE next_offset=GREATEST(next_offset,VALUES(next_offset))").param("run",r.runId().toString()).param("topic",r.topic()).param("partition",partition).param("next",next).update();if(status!=null&&r.runId().equals(status.runId())){var m=new TreeMap<>(status.nextOffsets());m.merge(partition,next,Math::max);status=snapshot(r,m,status.running(),status.failureClass());}}
    private void fail(Exception e){var r=active;if(r!=null)status=snapshot(r,status.nextOffsets(),false,e.getClass().getSimpleName());}
    private KafkaConsumer<String,String> createConsumer(UUID runId){var p=new Properties();p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG,bootstrap);p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,StringDeserializer.class);p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG,"false");p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG,"none");p.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG,"read_committed");p.put(ConsumerConfig.GROUP_ID_CONFIG,"rebuild-shadow-"+runId);return new KafkaConsumer<>(p);}
    @Override public ShadowReplayStatus status(UUID runId){var s=status;if(s==null||!runId.equals(s.runId()))throw new ShadowRunNotFoundException();return s;}
    @Override public synchronized ShadowReplayStatus stop(UUID runId){var s=status;if(s==null||!runId.equals(s.runId()))throw new ShadowRunNotFoundException();stopRequested.set(true);var c=consumer;if(c!=null)c.wakeup();var w=worker;if(w!=null){w.interrupt();try{w.join(Duration.ofSeconds(5));}catch(InterruptedException e){Thread.currentThread().interrupt();}if(w.isAlive())throw new IllegalStateException("shadow stop timeout");}if(status.running())status=snapshot(active,status.nextOffsets(),false,null);return status;}
    private static ShadowReplayStatus snapshot(ShadowReplayRequest r,Map<Integer,Long> offsets,boolean running,String failure){return new ShadowReplayStatus(r.runId(),r.target(),Set.copyOf(r.offsets().keySet()),Map.copyOf(offsets),running,failure);}
    private static final class RetryableShadowException extends RuntimeException {RetryableShadowException(String m){super(m);}RetryableShadowException(Throwable t){super(t);}}
}
