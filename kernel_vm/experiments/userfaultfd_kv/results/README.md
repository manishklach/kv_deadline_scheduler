# userfaultfd Results Status

No runtime result JSON was produced on the validated WSL run from 2026-06-17.

Observed environment facts:

```text
vm.unprivileged_userfaultfd = 0
sudo: a password is required
```

Interpretation:

- The experiment sources compile.
- This session could not elevate privileges to enable `userfaultfd`.
- Treat this as an environment block, not as a statement about the mechanism or the experiment design.

See:

- [../../../../docs/wsl_validation_2026_06_17.md](../../../../docs/wsl_validation_2026_06_17.md)
