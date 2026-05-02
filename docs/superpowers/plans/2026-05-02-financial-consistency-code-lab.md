# Financial Consistency Code Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `financial-consistency/09-code-lab/`, a self-contained Java 17 in-memory lab that generates abnormal financial histories, verifies consistency invariants, and prints explainable failure reports.

**Architecture:** The lab uses plain Java records and sealed interfaces to model `Command`, `Event`, `Fact`, `Fault`, `History`, and `InvariantViolation`. Verifiers read only history facts and never call business services. Generators create named scenarios, runners execute fixed and randomized experiments, and reports explain the violated invariant, related facts, and reduced failure history.

**Tech Stack:** Java 17, `javac`, `java`, POSIX shell scripts, no external dependencies, no database, no broker, no Spring Boot, no Gradle or Maven in this phase.

---

## Scope Check

The approved spec is one subsystem: the pure Java in-memory code lab. MySQL, Spring Boot, Kafka, Temporal, Testcontainers, and real service adapters are intentionally outside this plan. This plan produces working, testable software on its own.

## File Structure

Create these files:

- `financial-consistency/09-code-lab/README.md` - chapter entry point and learning path.
- `financial-consistency/09-code-lab/docs/01-running-the-lab.md` - commands and expected output.
- `financial-consistency/09-code-lab/docs/02-reading-failure-reports.md` - report field guide.
- `financial-consistency/09-code-lab/docs/03-mapping-to-real-systems.md` - how lab concepts map to MySQL, Outbox, Kafka, and Temporal later.
- `financial-consistency/09-code-lab/scripts/run-lab.sh` - compile and run the main runner.
- `financial-consistency/09-code-lab/scripts/test-lab.sh` - compile and run self-tests.
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/HistoryItem.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/Command.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/Event.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/Fact.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/Fault.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/FactType.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/History.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/InvariantViolation.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/ConsistencyVerifier.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/CompositeVerifier.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/LedgerConsistencyVerifier.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/StateMachineVerifier.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/ExternalFactVerifier.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/PropagationVerifier.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/ManualRepairVerifier.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/ExperimentCase.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/TransferHistoryGenerator.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/PaymentHistoryGenerator.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/OrderHistoryGenerator.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/TravelHistoryGenerator.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/report/FailureReport.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/report/FailureReporter.java`
- `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/runner/CodeLabRunner.java`
- `financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java`

Modify these files:

- `financial-consistency/README.md` - add the new `09-code-lab` phase and design spec link.

## Public Contracts

Use package `com.interview.financialconsistency.codelab`.

Core model contracts:

```java
public sealed interface HistoryItem permits Command, Event, Fact, Fault {
    String id();
    String businessKey();
    Instant occurredAt();
    Map<String, String> attributes();
    default String attr(String key) { return attributes().get(key); }
    default String requireAttr(String key) {
        String value = attributes().get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing attribute " + key + " on " + id());
        }
        return value;
    }
}
```

```java
public record Command(String id, String name, String businessKey, Instant occurredAt, Map<String, String> attributes)
        implements HistoryItem {}
```

```java
public record Event(String id, String name, String businessKey, Instant occurredAt, Map<String, String> attributes)
        implements HistoryItem {}
```

```java
public record Fact(String id, FactType type, String businessKey, Instant occurredAt, BigDecimal amount,
                   Map<String, String> attributes) implements HistoryItem {}
```

```java
public record Fault(String id, String name, String businessKey, Instant occurredAt, Map<String, String> attributes)
        implements HistoryItem {}
```

Verifier contract:

```java
public interface ConsistencyVerifier {
    String name();
    List<InvariantViolation> verify(History history);
}
```

Experiment contract:

```java
public record ExperimentCase(String name, String scenario, History history, boolean expectedToPass) {}
```

## Task 1: Scaffold A Runnable Plain Java Lab

**Files:**
- Create: `financial-consistency/09-code-lab/README.md`
- Create: `financial-consistency/09-code-lab/scripts/run-lab.sh`
- Create: `financial-consistency/09-code-lab/scripts/test-lab.sh`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/runner/CodeLabRunner.java`
- Create: `financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java`

- [ ] **Step 1: Run the missing smoke command**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected: fail because `test-lab.sh` does not exist.

- [ ] **Step 2: Create the run script**

Create `financial-consistency/09-code-lab/scripts/run-lab.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/out/main"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

find "$ROOT_DIR/src/main/java" -name '*.java' | sort > "$ROOT_DIR/out-main-sources.txt"
javac --release 17 -encoding UTF-8 -d "$OUT_DIR" @"$ROOT_DIR/out-main-sources.txt"
java -cp "$OUT_DIR" com.interview.financialconsistency.codelab.runner.CodeLabRunner "$@"
```

- [ ] **Step 3: Create the test script**

Create `financial-consistency/09-code-lab/scripts/test-lab.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/out/test"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

find "$ROOT_DIR/src/main/java" "$ROOT_DIR/src/test/java" -name '*.java' | sort > "$ROOT_DIR/out-test-sources.txt"
javac --release 17 -encoding UTF-8 -d "$OUT_DIR" @"$ROOT_DIR/out-test-sources.txt"
java -cp "$OUT_DIR" com.interview.financialconsistency.codelab.CodeLabSelfTest
```

- [ ] **Step 4: Create the minimal runner**

Create `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/runner/CodeLabRunner.java`:

```java
package com.interview.financialconsistency.codelab.runner;

public final class CodeLabRunner {
    private CodeLabRunner() {
    }

    public static void main(String[] args) {
        System.out.println("financial-consistency-code-lab");
    }
}
```

- [ ] **Step 5: Create the minimal self-test**

Create `financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java`:

```java
package com.interview.financialconsistency.codelab;

import com.interview.financialconsistency.codelab.runner.CodeLabRunner;

public final class CodeLabSelfTest {
    private CodeLabSelfTest() {
    }

    public static void main(String[] args) {
        CodeLabRunner.main(new String[0]);
        System.out.println("SELF_TEST_PASS");
    }
}
```

- [ ] **Step 6: Make scripts executable**

Run:

```bash
chmod +x financial-consistency/09-code-lab/scripts/run-lab.sh financial-consistency/09-code-lab/scripts/test-lab.sh
```

- [ ] **Step 7: Run smoke tests**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
bash financial-consistency/09-code-lab/scripts/run-lab.sh
```

Expected output includes:

```text
financial-consistency-code-lab
SELF_TEST_PASS
```

- [ ] **Step 8: Commit**

Run:

```bash
git add financial-consistency/09-code-lab
git commit -m "feat: scaffold financial consistency code lab"
```

## Task 2: Implement The Core History Model

**Files:**
- Create: all files under `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model/`
- Modify: `financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java`

- [ ] **Step 1: Add failing model tests**

Add these test calls to `CodeLabSelfTest.main`:

```java
testHistoryFiltersFacts();
testReducedHistoryKeepsSelectedItems();
testFactAttributesAreDefensiveCopies();
```

Add these methods:

```java
private static void testHistoryFiltersFacts() {
    History history = History.of(
            command("cmd-1", "CreateTransfer", "T1"),
            fact("fact-1", FactType.LEDGER_POSTING, "T1", "side", "DEBIT", "account", "A"),
            fact("fact-2", FactType.LOCAL_STATE, "T1", "state", "SUCCEEDED", "entity", "transfer:T1"));

    assertEquals(2, history.facts().size(), "history should expose two facts");
    assertEquals(1, history.facts(FactType.LEDGER_POSTING).size(), "history should filter ledger facts");
}

private static void testReducedHistoryKeepsSelectedItems() {
    History history = History.of(
            command("cmd-1", "CreateTransfer", "T1"),
            fact("fact-1", FactType.LEDGER_POSTING, "T1", "side", "DEBIT"),
            fact("fact-2", FactType.LEDGER_POSTING, "T1", "side", "CREDIT"));

    History reduced = history.reduceTo(Set.of("cmd-1", "fact-2"));
    assertEquals(2, reduced.items().size(), "reduced history should keep selected items");
    assertEquals("fact-2", reduced.items().get(1).id(), "reduced history should preserve original order");
}

private static void testFactAttributesAreDefensiveCopies() {
    Map<String, String> attributes = new LinkedHashMap<>();
    attributes.put("side", "DEBIT");
    Fact fact = new Fact("fact-1", FactType.LEDGER_POSTING, "T1", Instant.EPOCH, BigDecimal.TEN, attributes);
    attributes.put("side", "CREDIT");
    assertEquals("DEBIT", fact.requireAttr("side"), "fact should copy attributes at construction");
}
```

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected: fail because model classes do not exist.

- [ ] **Step 2: Implement model records and enum**

Create the model files using the public contracts above plus these concrete rules:

- `FactType` values: `LEDGER_POSTING`, `IDEMPOTENCY_RECORD`, `LOCAL_STATE`, `EXTERNAL_RESULT`, `OUTBOX_RECORD`, `OUTBOX_PUBLISHED`, `MESSAGE_HANDLED`, `BUSINESS_EFFECT`, `MANUAL_APPROVAL`, `MANUAL_REPAIR`, `MANUAL_REVIEW`, `SUPPLIER_RESULT`, `TCC_STAGE`.
- Every record constructor must replace null attribute maps with `Map.of()` and otherwise store `Map.copyOf(attributes)`.
- `Fact` must replace null amount with `BigDecimal.ZERO`.
- `History.of(HistoryItem... items)` must store `List.copyOf(Arrays.asList(items))`.
- `History.facts()` must return all `Fact` items in order.
- `History.facts(FactType type)` must filter by exact type.
- `History.factsByBusinessKey(String businessKey)` must filter facts by exact business key.
- `History.reduceTo(Set<String> ids)` must keep items whose `id()` is contained in the provided set, preserving original order.
- `InvariantViolation` fields: `String invariant`, `String reason`, `String verifier`, `String boundary`, `List<String> relatedItemIds`, `History reducedHistory`.

- [ ] **Step 3: Add test helpers**

Add these helpers to `CodeLabSelfTest`:

```java
private static Command command(String id, String name, String businessKey, String... attrs) {
    return new Command(id, name, businessKey, Instant.EPOCH, attrs(attrs));
}

private static Event event(String id, String name, String businessKey, String... attrs) {
    return new Event(id, name, businessKey, Instant.EPOCH, attrs(attrs));
}

private static Fact fact(String id, FactType type, String businessKey, String... attrs) {
    return new Fact(id, type, businessKey, Instant.EPOCH, BigDecimal.ZERO, attrs(attrs));
}

private static Fact moneyFact(String id, FactType type, String businessKey, BigDecimal amount, String... attrs) {
    return new Fact(id, type, businessKey, Instant.EPOCH, amount, attrs(attrs));
}

private static Map<String, String> attrs(String... values) {
    if (values.length % 2 != 0) {
        throw new IllegalArgumentException("attributes must be key/value pairs");
    }
    Map<String, String> result = new LinkedHashMap<>();
    for (int i = 0; i < values.length; i += 2) {
        result.put(values[i], values[i + 1]);
    }
    return result;
}

private static void assertEquals(Object expected, Object actual, String message) {
    if (!Objects.equals(expected, actual)) {
        throw new AssertionError(message + " expected=" + expected + " actual=" + actual);
    }
}

private static void assertTrue(boolean condition, String message) {
    if (!condition) {
        throw new AssertionError(message);
    }
}
```

- [ ] **Step 4: Run tests**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected output includes:

```text
SELF_TEST_PASS
```

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/model financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java
git commit -m "feat: add financial history model"
```

## Task 3: Add Verifier Interfaces, Reports, Ledger, And State Checks

**Files:**
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/ConsistencyVerifier.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/CompositeVerifier.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/LedgerConsistencyVerifier.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/StateMachineVerifier.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/report/FailureReport.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/report/FailureReporter.java`
- Modify: `financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java`

- [ ] **Step 1: Add failing verifier tests**

Add these calls:

```java
testLedgerVerifierRejectsUnbalancedTransfer();
testLedgerVerifierRejectsDuplicateBusinessEffect();
testStateMachineVerifierRejectsDualTerminalStates();
testFailureReporterPrintsViolationDetails();
```

Test rules:

- `testLedgerVerifierRejectsUnbalancedTransfer` builds a history with one `LEDGER_POSTING` debit of `100.00` and no matching credit. It expects one violation containing invariant `LEDGER_BALANCED`.
- `testLedgerVerifierRejectsDuplicateBusinessEffect` builds two `BUSINESS_EFFECT` facts with the same `effectKey=transfer:T1:debit`. It expects one violation containing invariant `BUSINESS_EFFECT_IDEMPOTENT`.
- `testStateMachineVerifierRejectsDualTerminalStates` builds two `LOCAL_STATE` facts for `entity=payment:P1`, one `state=SUCCEEDED` and one `state=FAILED`. It expects one violation containing invariant `STATE_MACHINE_SINGLE_TERMINAL`.
- `testFailureReporterPrintsViolationDetails` creates a `FailureReport` and asserts the rendered text contains `Violated invariant`, the verifier name, and a related fact id.

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected: fail because verifier and report classes do not exist.

- [ ] **Step 2: Implement verifier interfaces**

Implement `ConsistencyVerifier` from the public contract.

Implement `CompositeVerifier` with:

```java
public final class CompositeVerifier implements ConsistencyVerifier {
    private final List<ConsistencyVerifier> verifiers;

    public CompositeVerifier(List<ConsistencyVerifier> verifiers) {
        this.verifiers = List.copyOf(verifiers);
    }

    @Override
    public String name() {
        return "CompositeVerifier";
    }

    @Override
    public List<InvariantViolation> verify(History history) {
        List<InvariantViolation> violations = new ArrayList<>();
        for (ConsistencyVerifier verifier : verifiers) {
            violations.addAll(verifier.verify(history));
        }
        return List.copyOf(violations);
    }
}
```

- [ ] **Step 3: Implement `LedgerConsistencyVerifier`**

Rules:

- Group `LEDGER_POSTING` facts by `businessKey`.
- Each ledger posting uses `amount()` and `side` attribute.
- `side=DEBIT` subtracts amount.
- `side=CREDIT` adds amount.
- Any group whose signed sum is not zero creates `LEDGER_BALANCED`.
- Group `BUSINESS_EFFECT` facts by `effectKey`; count greater than one creates `BUSINESS_EFFECT_IDEMPOTENT`.
- Reduced history keeps the related posting or effect facts.

- [ ] **Step 4: Implement `StateMachineVerifier`**

Rules:

- Read `LOCAL_STATE` facts.
- Group by `entity` attribute.
- Terminal states are `SUCCEEDED`, `FAILED`, `CANCELLED`.
- If one entity has more than one distinct terminal state, create `STATE_MACHINE_SINGLE_TERMINAL`.
- If a fact has `state=FAILED` and the same business key also has an `EXTERNAL_RESULT` or `SUPPLIER_RESULT` with `result=UNKNOWN`, create `UNKNOWN_NOT_LOCAL_FAILURE`.

- [ ] **Step 5: Implement report classes**

`FailureReport` fields:

```java
String experimentName;
String scenario;
String seed;
boolean expectedToPass;
List<InvariantViolation> violations;
```

`FailureReporter.render(FailureReport report)` must include:

- `Experiment: <name>`
- `Scenario: <scenario>`
- `Seed: <seed>`
- `Result: PASS` or `Result: FAILED`
- `Violated invariant:` for each violation
- `Verifier: <verifier>`
- `Related items:` with ids
- `Reduced history:` with ordered item ids

- [ ] **Step 6: Run tests**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected output includes:

```text
SELF_TEST_PASS
```

- [ ] **Step 7: Commit**

Run:

```bash
git add financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/report financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java
git commit -m "feat: add core consistency verifiers"
```

## Task 4: Add External Fact, Propagation, And Manual Repair Verifiers

**Files:**
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/ExternalFactVerifier.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/PropagationVerifier.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier/ManualRepairVerifier.java`
- Modify: `financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java`

- [ ] **Step 1: Add failing tests**

Add these calls:

```java
testExternalFactVerifierRejectsLateSuccessAfterLocalFailure();
testPropagationVerifierRejectsCommittedOutboxWithoutPublication();
testPropagationVerifierRejectsDuplicateMessageEffect();
testManualRepairVerifierRejectsRepairWithoutApprovalAndReview();
testManualRepairVerifierRejectsDuplicateRepair();
```

Test rules:

- Late success: `LOCAL_STATE state=FAILED entity=payment:P1` plus `EXTERNAL_RESULT result=SUCCEEDED provider=card-network` for the same business key must produce `EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE`.
- Committed Outbox: `OUTBOX_RECORD messageId=M1 status=COMMITTED` without matching `OUTBOX_PUBLISHED messageId=M1` must produce `OUTBOX_COMMITTED_NOT_PUBLISHED`.
- Duplicate message effect: two `BUSINESS_EFFECT` facts with `messageId=M1` and the same `effectKey` must produce `MESSAGE_EFFECT_IDEMPOTENT`.
- Repair without approval and review: `MANUAL_REPAIR repairKey=R1` without `MANUAL_APPROVAL repairKey=R1` and `MANUAL_REVIEW repairKey=R1 result=APPROVED` must produce `MANUAL_REPAIR_REQUIRES_APPROVAL_AND_REVIEW`.
- Duplicate repair: two `MANUAL_REPAIR repairKey=R1` facts must produce `MANUAL_REPAIR_IDEMPOTENT`.

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected: fail because these verifier classes do not exist.

- [ ] **Step 2: Implement `ExternalFactVerifier`**

Rules:

- For each business key, if any `EXTERNAL_RESULT result=SUCCEEDED` or `SUPPLIER_RESULT result=SUCCEEDED` exists and any `LOCAL_STATE state=FAILED` exists, create `EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE`.
- Reduced history contains the external or supplier success fact plus the local failure fact.
- Boundary is `external-fact`.

- [ ] **Step 3: Implement `PropagationVerifier`**

Rules:

- For each `OUTBOX_RECORD`, read `messageId`.
- If `status=COMMITTED` and no `OUTBOX_PUBLISHED` fact has the same `messageId`, create `OUTBOX_COMMITTED_NOT_PUBLISHED`.
- For `BUSINESS_EFFECT` facts with a `messageId`, group by `messageId + ":" + effectKey`; if count greater than one, create `MESSAGE_EFFECT_IDEMPOTENT`.
- Boundary is `propagation`.

- [ ] **Step 4: Implement `ManualRepairVerifier`**

Rules:

- For each `MANUAL_REPAIR`, read `repairKey`.
- The same repair key must have at least one `MANUAL_APPROVAL`.
- The same repair key must have at least one `MANUAL_REVIEW` with `result=APPROVED`.
- Missing evidence creates `MANUAL_REPAIR_REQUIRES_APPROVAL_AND_REVIEW`.
- More than one `MANUAL_REPAIR` for the same `repairKey` creates `MANUAL_REPAIR_IDEMPOTENT`.
- Boundary is `manual-repair`.

- [ ] **Step 5: Run tests**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected output includes:

```text
SELF_TEST_PASS
```

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/verifier financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java
git commit -m "feat: add external propagation and repair verifiers"
```

## Task 5: Add Scenario Generators And The Eight Required Experiments

**Files:**
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/ExperimentCase.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/TransferHistoryGenerator.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/PaymentHistoryGenerator.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/OrderHistoryGenerator.java`
- Create: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator/TravelHistoryGenerator.java`
- Modify: `financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java`

- [ ] **Step 1: Add failing generator tests**

Add these calls:

```java
testGeneratorsExposeAtLeastEightCases();
testGeneratedFailureCasesProduceViolations();
testGeneratedPassingCasesProduceNoViolations();
```

Test rules:

- Collect all cases from the four generators.
- Assert there are at least eight cases.
- Assert these exact case names exist:
  - `transfer-duplicate-request`
  - `transfer-unbalanced-ledger`
  - `payment-timeout-late-success`
  - `outbox-committed-not-published`
  - `consumer-duplicate-message-effect`
  - `tcc-cancel-confirm-race`
  - `travel-flight-success-hotel-failed`
  - `manual-repair-duplicate-submit`
- Use `CompositeVerifier` with all five verifier classes.
- Every `expectedToPass=false` case must produce at least one violation.
- Every `expectedToPass=true` case must produce zero violations.

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected: fail because generator classes do not exist.

- [ ] **Step 2: Implement `ExperimentCase`**

Use this record:

```java
package com.interview.financialconsistency.codelab.generator;

import com.interview.financialconsistency.codelab.model.History;

public record ExperimentCase(String name, String scenario, History history, boolean expectedToPass) {
}
```

- [ ] **Step 3: Implement `TransferHistoryGenerator`**

Cases:

- `transfer-normal-balanced` expected pass: command, idempotency fact, debit ledger posting `side=DEBIT amount=100.00`, credit ledger posting `side=CREDIT amount=100.00`, local state `SUCCEEDED`.
- `transfer-duplicate-request` expected fail: two `BUSINESS_EFFECT` facts with `effectKey=transfer:T1:debit`.
- `transfer-unbalanced-ledger` expected fail: debit ledger posting `100.00` without credit.

- [ ] **Step 4: Implement `PaymentHistoryGenerator`**

Cases:

- `payment-timeout-unknown-then-success` expected pass: command, local state `UNKNOWN`, external result `SUCCEEDED`, local state `SUCCEEDED`.
- `payment-timeout-late-success` expected fail: command, local state `FAILED`, external result `SUCCEEDED`.
- `outbox-committed-not-published` expected fail: local state `SUCCEEDED`, `OUTBOX_RECORD messageId=M1 status=COMMITTED`, no published fact.
- `consumer-duplicate-message-effect` expected fail: two `BUSINESS_EFFECT` facts with `messageId=M2 effectKey=payment:P2:settled`.

- [ ] **Step 5: Implement `OrderHistoryGenerator`**

Cases:

- `order-paid-inventory-failed` expected fail: local state `SUCCEEDED entity=payment:P3`, local state `FAILED entity=order:O3`, external result `SUCCEEDED`.
- `tcc-cancel-confirm-race` expected fail: two `LOCAL_STATE` facts for `entity=tcc:TCC1`, one `state=SUCCEEDED` and one `state=CANCELLED`.

- [ ] **Step 6: Implement `TravelHistoryGenerator`**

Cases:

- `travel-flight-success-hotel-failed` expected fail: supplier result `SUCCEEDED component=flight`, local state `FAILED entity=trip:TR1`, no manual repair.
- `travel-manual-repair-reviewed` expected pass: supplier result `SUCCEEDED`, manual approval, manual repair, manual review `result=APPROVED`.
- `manual-repair-duplicate-submit` expected fail: approval and review exist, but two manual repair facts use the same `repairKey=R-DUP`.

- [ ] **Step 7: Run tests**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected output includes:

```text
SELF_TEST_PASS
```

- [ ] **Step 8: Commit**

Run:

```bash
git add financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/generator financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java
git commit -m "feat: add financial consistency scenario generators"
```

## Task 6: Implement Runner CLI And Explainable Reports

**Files:**
- Modify: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/runner/CodeLabRunner.java`
- Modify: `financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/report/FailureReporter.java`
- Modify: `financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java`

- [ ] **Step 1: Add failing CLI tests**

Add these calls:

```java
testRunnerListsCases();
testRunnerRunsOneCase();
testRunnerRunsAllCases();
```

Test rules:

- `CodeLabRunner.run(new String[]{"list"})` returns text containing `transfer-duplicate-request` and `manual-repair-duplicate-submit`.
- `CodeLabRunner.run(new String[]{"run", "--case", "payment-timeout-late-success"})` returns text containing `Experiment: payment-timeout-late-success`, `Result: FAILED`, and `ExternalFactVerifier`.
- `CodeLabRunner.run(new String[]{"run"})` returns text containing `Summary:` and `expectedFailures=8`.

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected: fail because `CodeLabRunner.run` does not exist.

- [ ] **Step 2: Implement `CodeLabRunner.run`**

Rules:

- `main` prints `run(args)`.
- `list` returns one line per case: `<name> [<scenario>] expected=<PASS|FAIL>`.
- `run --case <name>` runs exactly one case.
- `run` with no arguments runs all cases.
- Unknown command returns a usage string containing `Usage:`.
- Unknown case returns a string containing `Unknown case: <name>`.
- Summary fields: `total`, `expectedPasses`, `expectedFailures`, `actualFailures`.

- [ ] **Step 3: Build default verifier and case registry**

`CodeLabRunner` must create:

```java
CompositeVerifier verifier = new CompositeVerifier(List.of(
        new LedgerConsistencyVerifier(),
        new StateMachineVerifier(),
        new ExternalFactVerifier(),
        new PropagationVerifier(),
        new ManualRepairVerifier()));
```

Collect cases from:

```java
new TransferHistoryGenerator().cases()
new PaymentHistoryGenerator().cases()
new OrderHistoryGenerator().cases()
new TravelHistoryGenerator().cases()
```

- [ ] **Step 4: Render reports for each case**

For each case:

- Run verifier.
- Build `FailureReport` with seed `fixed:<caseName>`.
- Render report when actual violations are not empty.
- For passing cases, print `Experiment: <name>` and `Result: PASS`.
- After all cases, print summary.

- [ ] **Step 5: Run tests and CLI manually**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
bash financial-consistency/09-code-lab/scripts/run-lab.sh list
bash financial-consistency/09-code-lab/scripts/run-lab.sh run --case payment-timeout-late-success
bash financial-consistency/09-code-lab/scripts/run-lab.sh run
```

Expected output includes:

```text
SELF_TEST_PASS
payment-timeout-late-success
Result: FAILED
Summary:
expectedFailures=8
```

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/runner financial-consistency/09-code-lab/src/main/java/com/interview/financialconsistency/codelab/report financial-consistency/09-code-lab/src/test/java/com/interview/financialconsistency/codelab/CodeLabSelfTest.java
git commit -m "feat: add code lab runner reports"
```

## Task 7: Add Chapter Documentation And Root Route Link

**Files:**
- Modify: `financial-consistency/09-code-lab/README.md`
- Create: `financial-consistency/09-code-lab/docs/01-running-the-lab.md`
- Create: `financial-consistency/09-code-lab/docs/02-reading-failure-reports.md`
- Create: `financial-consistency/09-code-lab/docs/03-mapping-to-real-systems.md`
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Add doc verification command before editing**

Run:

```bash
test -f financial-consistency/09-code-lab/README.md
test -f financial-consistency/README.md
```

Expected: both commands exit with status 0.

- [ ] **Step 2: Write `09-code-lab/README.md`**

Include these sections:

- `# 09 代码实验室`
- `## 目标`
- `## 运行方式`
- `## 学习顺序`
- `## 实验列表`
- `## 关键边界`

The boundary section must state:

```text
这里的 verifier 是一致性判定器，不是 Oracle 数据库。MySQL 会在后续真实工程阶段作为事实存储和事务实验对象出现，但不能替代独立判定器。
```

- [ ] **Step 3: Write running docs**

`docs/01-running-the-lab.md` must include exact commands:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
bash financial-consistency/09-code-lab/scripts/run-lab.sh list
bash financial-consistency/09-code-lab/scripts/run-lab.sh run --case payment-timeout-late-success
bash financial-consistency/09-code-lab/scripts/run-lab.sh run
```

- [ ] **Step 4: Write report docs**

`docs/02-reading-failure-reports.md` must explain these fields:

- `Experiment`
- `Scenario`
- `Seed`
- `Result`
- `Violated invariant`
- `Relevant facts`
- `Reduced history`
- `Verifier`
- `Interpretation`

Use `payment-timeout-late-success` as the example.

- [ ] **Step 5: Write mapping docs**

`docs/03-mapping-to-real-systems.md` must include this mapping table:

| Lab concept | Real system counterpart |
| --- | --- |
| `Fact` | MySQL row, channel statement row, broker delivery record, workflow history event |
| `History` | Ordered evidence collected from DB, broker, logs, channel files, and audit tables |
| `ConsistencyVerifier` | Independent reconciliation or invariant checker |
| `Generator` | Property test, replay test, or fault injection fixture |
| `InvariantViolation` | Reconciliation difference, audit finding, or test failure report |

- [ ] **Step 6: Update root README**

Add the new design spec link:

```markdown
- [2026-05-02-financial-consistency-code-lab-design.md](../docs/superpowers/specs/2026-05-02-financial-consistency-code-lab-design.md)
```

Add the new stage after `08-interview-synthesis`:

```markdown
- [09-code-lab](./09-code-lab/README.md)
  纯 Java 内存代码实验室：模型、异常历史、一致性判定器、runner 和可解释失败报告。
```

- [ ] **Step 7: Run docs and lab verification**

Run:

```bash
rg -n "09-code-lab|financial-consistency-code-lab-design|一致性判定器" financial-consistency/README.md financial-consistency/09-code-lab
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected output includes:

```text
09-code-lab
financial-consistency-code-lab-design
一致性判定器
SELF_TEST_PASS
```

- [ ] **Step 8: Commit**

Run:

```bash
git add financial-consistency/README.md financial-consistency/09-code-lab/README.md financial-consistency/09-code-lab/docs
git commit -m "docs: document financial consistency code lab"
```

## Task 8: Final Verification And Scope Guard

**Files:**
- Modify only if verification reveals a concrete mismatch in files created or modified by Tasks 1-7.

- [ ] **Step 1: Run full lab tests**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/test-lab.sh
```

Expected output includes:

```text
SELF_TEST_PASS
```

- [ ] **Step 2: Run full lab CLI**

Run:

```bash
bash financial-consistency/09-code-lab/scripts/run-lab.sh run
```

Expected output includes:

```text
Summary:
expectedFailures=8
actualFailures=8
```

- [ ] **Step 3: Confirm no infrastructure slipped into the phase**

Run:

```bash
rg -n "Spring Boot|Kafka|Temporal|Testcontainers|jdbc|mysql|postgres|oracle" financial-consistency/09-code-lab/src financial-consistency/09-code-lab/scripts
```

Expected: no matches.

- [ ] **Step 4: Confirm naming avoids Oracle database confusion**

Run:

```bash
rg -n "Oracle" financial-consistency/09-code-lab
```

Expected: matches only in documentation sentences that explicitly say the verifier is not Oracle Database.

- [ ] **Step 5: Confirm route link exists**

Run:

```bash
rg -n "09-code-lab|financial-consistency-code-lab-design" financial-consistency/README.md
```

Expected output includes both strings.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short --branch
```

Expected: only known unrelated pre-existing changes remain outside `financial-consistency/09-code-lab` and `financial-consistency/README.md`.

- [ ] **Step 7: Commit final fixes if any were needed**

If files changed during Task 8, run:

```bash
git add financial-consistency/09-code-lab financial-consistency/README.md
git commit -m "chore: verify financial consistency code lab"
```

If no files changed during Task 8, do not create an empty commit.

## Self-Review Checklist

- Spec coverage: model, verifiers, generators, runner, reports, docs, and root navigation are covered.
- Scope guard: no database, broker, Spring Boot, Temporal, Testcontainers, Gradle, Maven, or external dependency is introduced.
- Naming guard: Java code uses `ConsistencyVerifier`; docs explicitly explain that verifier is not Oracle Database.
- Testability: every implementation task has a failing test or failing command before code, a passing command after code, and a commit step.
- Reproducibility: all verification commands use paths inside `financial-consistency/09-code-lab`.
