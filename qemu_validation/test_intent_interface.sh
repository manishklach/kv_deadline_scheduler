#!/bin/bash
set -euo pipefail

mount -t debugfs none /sys/kernel/debug || true

if [[ ! -d /sys/kernel/debug/mm_intent ]]; then
  echo "FAIL: /sys/kernel/debug/mm_intent missing"
  exit 1
fi

echo "1 0x7f000000 0x400000 0x1 5000000 3" > /sys/kernel/debug/mm_intent/register

if ! cat /sys/kernel/debug/mm_intent/dump | grep -q "0x1"; then
  echo "FAIL: registered region not visible in dump"
  exit 1
fi

if [[ -f /root/kv_damon_to_intent.py ]]; then
  python3 /root/kv_damon_to_intent.py || true
fi

echo "PASS: debugfs memory intent interface responds"
