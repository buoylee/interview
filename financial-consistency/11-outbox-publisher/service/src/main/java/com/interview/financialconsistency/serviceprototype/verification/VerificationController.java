package com.interview.financialconsistency.serviceprototype.verification;

import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/verification")
public class VerificationController {
    private final MysqlFactExtractor extractor;
    private final TransferMysqlVerifier verifier;

    public VerificationController(MysqlFactExtractor extractor, TransferMysqlVerifier verifier) {
        this.extractor = extractor;
        this.verifier = verifier;
    }

    @GetMapping("/violations")
    public List<DbInvariantViolation> violations() {
        return verifier.verify(extractor.extractAll());
    }
}
