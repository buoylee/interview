# Agent Runtime File Context Design

## Context

We are designing a developer-platform style Agent Runtime. The first MVP is read-only: it can use uploaded files, project resources, library resources, knowledge retrieval, and read-only tools, but it does not perform write actions.

The immediate design question is narrow:

> In a session, when should uploaded or stored files participate in the current turn, which files should be selected, and when should their content be injected into the model context?

The answer must be deterministic enough to debug and safe enough for multi-user production systems. File use cannot be left to the model guessing from natural language alone.

## Goals

- Treat uploaded files as resources, not as permanent prompt text.
- Define when a file becomes available, selected, injected, and active.
- Define trigger rules for selecting files in a user turn.
- Define when the runtime must ask a clarifying question instead of guessing.
- Define injection modes: metadata only, full text, summary, retrieved chunks, and multi-document planning.
- Keep session, project, and library resources from polluting unrelated turns.
- Record enough trace data to explain why files were selected or excluded.

## Non-Goals

- Do not design write tools, approval flows, or rollback.
- Do not choose a specific vector database, embedding model, or parsing vendor.
- Do not design a full long-term memory system.
- Do not make project or library knowledge automatically enter every request.
- Do not rely on prompt-only behavior for permissions, file boundaries, or ambiguity handling.

## Core Principle

File upload only makes a file available. It does not automatically make the file part of the model context.

```text
Uploaded file -> Available resource
User intent + resolver -> Selected resource
Task planner + token budget -> Injected context
Turn trace -> Active file focus for follow-up turns
```

The runtime owns selection boundaries. Retrieval owns relevance inside those boundaries. The model owns reasoning and generation over the context it receives.

## File States

### Available

A file is available when it exists in a resource pool and the current user is allowed to access it.

Examples:

- A file attached to the current session.
- A file saved to the current project.
- A file in a user or team library.

Available does not mean injected.

### Selected

A file is selected when the Resource Resolver determines that the current user turn should use that file.

Examples:

- Current message attachment: user uploads `A.pdf` and asks "summarize this file".
- Explicit filename: user says "compare `A.pdf` and `B.docx`".
- Active reference: user says "what risks does that file mention?" after the previous turn used `A.pdf`.

Selected does not mean full-text injection.

### Injected

A file is injected when some representation of it enters the current model input.

Possible injected forms:

- File metadata only.
- Whole extracted text.
- File-level summary.
- Retrieved chunks.
- Table-specific extracted rows.
- Image/OCR snippets.

### Active

A file becomes active when it was selected in a recent high-confidence turn and should be available for follow-up references like "that file", "the second document", or "the attachment".

Active file focus is session state. It should decay or reset when the user changes topic, uploads new files, or corrects the reference.

## Resource Scopes

The runtime supports three resource scopes:

| Scope | Meaning | Default Use |
|-------|---------|-------------|
| `session` | Files attached to the current chat or session | Considered for current and follow-up turns |
| `project` | Files saved to the current project workspace | Considered only when project context is explicit or configured |
| `library` | User/team/org-level reusable knowledge | Considered only when library or knowledge-base context is explicit or configured |

Scope determines the candidate pool. It does not determine injection.

Recommended default behavior:

- If the current message has attachments, use only those attachments unless the user explicitly asks for project or library context.
- Project resources should not override current attachments.
- Library resources should not be searched by default for ordinary chat turns.
- Project/library search must be traceable and preferably visible in the answer when it materially affects the result.

## Runtime Flow

```text
user message
-> collect candidate resources
-> detect file intent
-> resolve file ids
-> confidence gate
-> choose injection mode
-> assemble context
-> call model
-> write trace
-> update active file focus
```

## Candidate Collection

The runtime collects candidates in priority order:

1. Current message attachments.
2. Explicitly mentioned session files.
3. Session focus:
   - Current session active files.
   - Previous turn resolved files as a fallback only when active file focus is missing or stale.
4. Project files, only if project context is explicit or enabled.
5. Library files, only if library context is explicit or enabled.

`previous_turn.resolved_files` is a trace fact. `active_files` is the current focus state derived from trace and runtime policy. They should not be treated as two equal candidate pools. In the normal path, active focus already represents the useful subset of previous turn file references.

Hard filters are always applied before ranking:

- Tenant boundary.
- User/team permission.
- Project membership.
- File processing status is usable.
- Resource is not deleted or expired.
- Resource scope is allowed for this turn.

Soft ranking can use:

- Current attachment status.
- Explicit filename match.
- Alias match.
- Recency.
- Previous turn usage.
- Active/pinned status.
- Semantic similarity between user text and file metadata or summary.

## File Intent Detection

The runtime classifies each user turn into one of these intent classes.

### No File Intent

The user asks a general question and does not refer to files or knowledge sources.

Examples:

```text
Explain what RAG is.
Help me write a Python script.
What is the difference between BM25 and vector search?
```

Decision:

```text
Do not select files.
Do not retrieve from project or library.
```

### Explicit File Intent

The user directly asks to use file content.

Examples:

```text
Summarize this file.
Compare A.pdf and B.docx.
Extract the payment terms from the contract.
Does the attachment mention refund rules?
List the risks in these documents.
```

Decision:

```text
Select files from current attachments or explicit filename matches.
Proceed if confidence is high.
Ask if references are ambiguous.
```

### Deictic File Intent

The user uses contextual references.

Examples:

```text
What about the second file?
Does that document mention security risks?
Continue summarizing it.
What did the attachment say about pricing?
```

Decision:

```text
Resolve against active files or previous turn resolved files.
Ask if no active file set exists or if multiple interpretations are plausible.
```

### Project Or Library Intent

The user explicitly asks for broader stored knowledge.

Examples:

```text
Use the project docs to answer this.
Search our knowledge base for the deployment process.
According to the team library, what is the refund policy?
```

Decision:

```text
Open the project or library candidate pool.
Apply permission filters.
Retrieve only relevant resources or chunks.
```

### File Use Forbidden

The user explicitly says not to use files or knowledge sources.

Examples:

```text
Do not use the attachment.
Answer from general knowledge only.
Do not search the project docs.
```

Decision:

```text
Do not select files, even if active files exist.
Record the exclusion reason in trace.
```

## Selection Rules

Rules are evaluated before any LLM-assisted resolver.

### Rule 1: Current Attachments Win

If the current message includes attachments and the user has file intent, select those attachments.

```text
attachments=[A, B]
message="Summarize these files"
selected=[A, B]
reason=current_message_attachments
```

Project and library resources should not be searched unless explicitly requested.

### Rule 2: Explicit Names Win Over Active Files

If the user names a file, select the matching file even if another file is active.

```text
active=[A]
message="Now summarize B.pdf"
selected=[B]
reason=explicit_filename
```

If multiple files match the same name or alias, ask a clarifying question.

### Rule 3: Deictic References Use Active Files

If the user says "this file", "that document", "the attachment", or "the second file", resolve against active files and previous turn file references.

```text
previous_turn.resolved_resources=[A, B]
message="What about the second file?"
selected=[B]
reason=ordinal_reference_to_active_files
```

If active files are missing or stale, ask.

### Rule 4: Project And Library Are Opt-In

Project and library resources are included only when:

- The user explicitly asks for project/library/knowledge-base context.
- The product mode has a visible setting that enables project/library context for the session.
- A configured agent profile states that a specific knowledge base is always in scope.

Even then, candidate resources must be filtered by permission and ranked by relevance.

### Rule 5: Too Much Ambiguity Requires Clarification

The runtime should ask a clarification question when:

- The user says "these files" but there are no current attachments and no active file set.
- More than five candidate files match a vague reference.
- Multiple files share a filename or alias.
- The selected file confidence is below threshold.
- Project/library scope is too broad and the user did not specify topic or source.

The system should not silently choose a large or ambiguous resource set.

## Injection Planning

After selecting files, the runtime chooses how to represent them in model context.

### Metadata Only

Use when the model needs file identity but not content.

Examples:

- Asking which files are currently attached.
- Asking whether indexing is complete.
- Disambiguation prompt.

### Full Text

Use only when:

- The extracted text fits comfortably within the file-context budget.
- The task requires broad coverage.
- The file is small enough that retrieval would create more risk than benefit.

Examples:

- Summarizing a short text file.
- Translating a short uploaded document.

### File Summary

Use when:

- The user asks a broad question over a medium or large document.
- The runtime has a reliable precomputed or freshly generated summary.
- The answer does not need exact quotes or citations from every section.

Examples:

- "What is this document about?"
- "Give me an executive summary."

### Retrieved Chunks

Use when:

- The user asks a targeted question.
- The document is large.
- Exact grounding matters.
- Multiple files may contain related information.

Examples:

- "Does the contract mention termination penalties?"
- "Find the refund SLA in the policy documents."

### Map-Reduce Summary

Use when:

- The user asks for a complete summary of a large file.
- The full document cannot fit in context.
- Coverage matters more than answering one precise query.

Flow:

```text
split document
-> summarize chunks or sections
-> combine section summaries
-> generate final summary
-> cite source structure when useful
```

### Multi-Document Planning

Use when:

- The user asks to compare or synthesize multiple files.
- Each file may need independent retrieval or summarization before alignment.

Flow:

```text
resolve files
-> build per-file summaries or relevant chunk sets
-> align by topic
-> generate comparison or synthesis
```

## Context Budget Policy

The context assembler should reserve budget for:

- System and developer instructions.
- Current user message.
- Short recent conversation history.
- Active task state.
- Selected file context.
- Tool results, if any.
- Response budget.

File context should have an explicit cap. The runtime should prefer high-signal summaries or chunks over dumping large text.

Recommended MVP policy:

```text
If selected file text <= small_file_token_limit:
  allow full-text injection for broad tasks
Else if task is broad summary:
  use map-reduce summary
Else:
  use chunk retrieval + rerank
```

## Active File Focus

After each turn, the runtime updates active file focus.

Set active files when:

- The current turn selected files with high confidence.
- The model answer materially used file content.

Replace active files when:

- The user uploads new files and asks a file-related question.
- The user explicitly switches to another file.

Decay active files when:

- Several turns pass without file references.
- The user shifts to unrelated general discussion.
- The user disables file use.

Clear or correct active files when:

- The user says the runtime used the wrong file.
- The selected resource is deleted or access is revoked.

## Trace Requirements

Every turn should record a file context trace.

Minimum fields:

```text
turn_id
session_id
user_message_id
file_intent
candidate_resource_ids
selected_resource_ids
selection_reasons
selection_confidence
excluded_resource_ids
exclusion_reasons
injection_mode
injected_chunk_ids
injected_summary_ids
token_usage_by_context_type
active_files_before
active_files_after
clarification_required
```

Trace is required for:

- Debugging wrong-file answers.
- Explaining why project/library files were or were not used.
- Replaying RAG failures.
- Evaluating resolver quality.
- Auditing permission boundaries.

## Safety Rules

- File content is untrusted context. It must not be injected as system or developer instructions.
- File selection must respect storage-layer and retrieval-layer permissions, not prompt-only permissions.
- Project and library resources must not leak across tenants, users, or projects.
- Prompt injection inside files should be treated as document content, not runtime instruction.
- Sensitive data should be redacted before trace logging when required.
- User preference to "use this file in future" does not grant broader permissions.

## MVP Rules

The first read-only runtime should implement these rules:

1. Default to no file use.
2. Current message attachments plus file intent select current attachments.
3. Explicit filename references select matching files.
4. Deictic references resolve only against active files or previous turn files.
5. Project/library search is opt-in per turn or visible session setting.
6. Ambiguous references trigger clarification.
7. Small files can be injected as full text for broad tasks.
8. Large files use summary or retrieval planning.
9. Every selected and injected file is recorded in trace.
10. Active files are updated after high-confidence file turns.

## Open Decisions

These can be decided during implementation planning:

- Exact confidence threshold for resolver decisions.
- Exact file count threshold for clarification.
- Token limits for small-file full-text injection.
- Active file decay policy: turn count, time-based, or topic-shift classifier.
- Whether project/library opt-in is per message, per session, or per agent profile.
- Whether file summaries are generated eagerly at upload time or lazily on first use.

## Recommended Architecture

Use a rule-first resolver with optional LLM-assisted disambiguation:

```text
FileIntentClassifier
CandidateCollector
ResourceResolver
ConfidenceGate
RetrievalPlanner
ContextAssembler
TraceWriter
ActiveFileManager
```

Rules enforce boundaries and permissions. LLM assistance may help interpret ambiguous natural language inside the already-filtered candidate pool, but it must not expand the pool beyond permitted resources.

## Success Criteria

- A newly uploaded file is not injected unless the user asks a file-related question.
- "Summarize these files" with current attachments selects only those attachments.
- "That file" works after a file-focused turn and asks for clarification without active files.
- General questions do not search session, project, or library files by default.
- Project/library files are used only when explicitly requested or visibly enabled.
- Large files do not get blindly dumped into the prompt.
- Trace can explain each selected file, excluded file, injected chunk, and active file update.
