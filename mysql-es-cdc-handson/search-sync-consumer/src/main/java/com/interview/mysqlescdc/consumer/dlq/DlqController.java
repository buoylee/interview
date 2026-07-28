package com.interview.mysqlescdc.consumer.dlq;

import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class DlqController {
    private final DlqStore products; private final RecordDlqStore records;
    private final DlqReplayService productReplay; private final RecordDlqReplayService recordReplay;
    public DlqController(DlqStore products, RecordDlqStore records,
            DlqReplayService productReplay, RecordDlqReplayService recordReplay) {
        this.products=products; this.records=records; this.productReplay=productReplay; this.recordReplay=recordReplay;
    }
    @GetMapping("/internal/dlq") public List<DlqRecord> products(@RequestParam String status) {
        requirePending(status); return products.listPending();
    }
    @GetMapping("/internal/dlq/count") public Map<String,Long> productCount() {
        return Map.of("unresolved",products.unresolvedCount());
    }
    @PostMapping("/internal/dlq/{eventId}/replay") public ReplayResult replayProduct(@PathVariable String eventId) {
        return productReplay.replay(eventId);
    }
    @GetMapping("/internal/record-dlq") public List<RecordDlqRecord> records(@RequestParam String status) {
        requirePending(status); return records.listPending();
    }
    @GetMapping("/internal/record-dlq/count") public Map<String,Long> recordCount() {
        return Map.of("unresolved",records.unresolvedCount());
    }
    @PostMapping("/internal/record-dlq/{recordId}/replay") public RecordReplayResult replayRecord(@PathVariable String recordId) {
        return recordReplay.replay(recordId);
    }
    private static void requirePending(String status) {
        if(!"PENDING".equals(status))
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "only status=PENDING is supported");
    }
}
