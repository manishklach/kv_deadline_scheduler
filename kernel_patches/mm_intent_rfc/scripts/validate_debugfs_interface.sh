#!/bin/bash
set -e

ROOT="/sys/kernel/debug/mm_intent"

if [[ ! -d "$ROOT" ]]; then
  echo "missing $ROOT"
  echo "mount debugfs and boot the patched kernel first"
  exit 1
fi

for name in register dump clear; do
  if [[ ! -e "$ROOT/$name" ]]; then
    echo "missing $ROOT/$name"
    exit 1
  fi
done

echo "mm_intent debugfs interface present"

if [[ "$1" == "--pid" ]]; then
  PID="$2"
  if [[ "$3" != "--addr" ]]; then
    echo "usage: $0 [--pid <pid> --addr <start_hex> --length <len_hex> --flags <flags_hex> --deadline <ns> --priority <prio>]"
    exit 1
  fi
  ADDR="$4"
  if [[ "$5" != "--length" ]]; then
    echo "missing --length"
    exit 1
  fi
  LENGTH="$6"
  if [[ "$7" != "--flags" ]]; then
    echo "missing --flags"
    exit 1
  fi
  FLAGS="$8"
  if [[ "$9" != "--deadline" ]]; then
    echo "missing --deadline"
    exit 1
  fi
  DEADLINE="${10}"
  if [[ "${11}" != "--priority" ]]; then
    echo "missing --priority"
    exit 1
  fi
  PRIORITY="${12}"

  echo "$PID $ADDR $LENGTH $FLAGS $DEADLINE $PRIORITY" > "$ROOT/register"
  echo "registered test range"
  cat "$ROOT/dump"
  exit 0
fi

echo "to test registration:"
echo "  $0 --pid <pid> --addr <start_hex> --length <len_hex> --flags <flags_hex> --deadline <ns> --priority <prio>"
