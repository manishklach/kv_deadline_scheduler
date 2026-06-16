#!/usr/bin/env bash
set -euo pipefail

PID="${1:-}"
DURATION="${2:-60}"

if [[ -z "$PID" ]]; then
  echo "Usage: $0 <pid> [duration-sec]"
  exit 1
fi

echo "Checking for DAMON control interfaces..."

if [[ -d /sys/kernel/mm/damon/admin ]]; then
  echo "Found DAMON sysfs admin interface at /sys/kernel/mm/damon/admin"
  echo "Kernel support varies by distro and version."
  echo "Suggested next steps for PID $PID over about $DURATION seconds:"
  echo "  1. Inspect available DAMON admin controls under /sys/kernel/mm/damon/admin"
  echo "  2. Create or select a context that targets PID $PID"
  echo "  3. Configure monitoring duration close to $DURATION seconds"
  echo "  4. Collect hot and cold region observations for comparison"
  exit 0
fi

if [[ -d /sys/kernel/debug/damon ]]; then
  echo "Found DAMON debugfs interface at /sys/kernel/debug/damon"
  echo "You may need debugfs mounted and distro-specific DAMON tooling."
  echo "Suggested next steps for PID $PID over about $DURATION seconds:"
  echo "  1. Confirm debugfs DAMON support on this kernel"
  echo "  2. Target PID $PID with the available DAMON interface"
  echo "  3. Collect region-hotness output during the run"
  exit 0
fi

echo "DAMON control interface not detected."
echo "Ensure CONFIG_DAMON and CONFIG_DAMON_SYSFS or debugfs support are enabled."
echo "Common paths to look for are:"
echo "  /sys/kernel/mm/damon/admin"
echo "  /sys/kernel/debug/damon"
echo "If unavailable, consult your distro kernel config or DAMON documentation."
