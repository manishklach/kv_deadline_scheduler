# Request Trace Format

External request traces are JSONL records shaped like `RequestTraceRecord`.

Example:

```json
{"request_id":"interactive-1","arrival_ms":0,"start_ms":5,"end_ms":3000,"prompt_tokens":4096,"generated_tokens":512,"request_priority":90,"deadline_ms":2500,"model_name":"llama-3-8b","status":"completed"}
```

Fields:

- `request_id`: stable request identifier
- `arrival_ms`: request arrival time
- `start_ms`: optional scheduling or service start time
- `end_ms`: optional completion time
- `prompt_tokens`: prompt length
- `generated_tokens`: generated output tokens
- `request_priority`: 0 to 100 urgency hint
- `deadline_ms`: optional request deadline
- `model_name`: optional model preset hint
- `status`: request status such as `completed`

Imported traces are approximate. KV Deadline Scheduler reconstructs logical KV blocks from request sizes and model configuration rather than reading runtime-internal allocation events.
