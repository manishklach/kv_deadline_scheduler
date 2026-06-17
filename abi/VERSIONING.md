# ABI Versioning Policy

- The ABI starts at version `1`.
- Existing fields never move.
- Existing field meanings do not change.
- New fields append at the end of the struct.
- Any wire-format or layout change requires a version bump.
- Existing users must continue to function when new fields are appended and ignored.
- JSONL traces may grow additional keys; binary paths must preserve offsets for existing fields.
