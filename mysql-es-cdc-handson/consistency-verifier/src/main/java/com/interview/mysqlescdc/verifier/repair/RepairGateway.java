package com.interview.mysqlescdc.verifier.repair;

import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;

public interface RepairGateway {
    RepairOutcome write(String target, RepairActionType type, ExpectedDocument document);

    RepairOutcome deleteExtra(String target, IndexedDocument observed);
}
