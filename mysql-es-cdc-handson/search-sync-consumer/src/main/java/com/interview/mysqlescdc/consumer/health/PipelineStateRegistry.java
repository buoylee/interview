package com.interview.mysqlescdc.consumer.health;

import java.util.concurrent.atomic.AtomicBoolean;
import org.springframework.stereotype.Component;
import com.interview.mysqlescdc.consumer.dlq.*;

@Component
public class PipelineStateRegistry {
    private final DlqStore products; private final RecordDlqStore records;
    private final AtomicBoolean catchingUp=new AtomicBoolean();
    public PipelineStateRegistry(DlqStore products, RecordDlqStore records) {
        this.products=products; this.records=records;
    }
    public PipelineState current() {
        if(products.unresolvedCount()>0 || records.unresolvedCount()>0) return PipelineState.DEGRADED;
        return catchingUp.get()?PipelineState.CATCHING_UP:PipelineState.HEALTHY;
    }
    public void setCatchingUp(boolean value) { catchingUp.set(value); }
}
