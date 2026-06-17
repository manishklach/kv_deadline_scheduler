#!/bin/bash
set -euo pipefail

KERNEL_URL="https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.8.12.12.tar.xz"
BUILDROOT_URL="https://buildroot.org/downloads/buildroot-2024.02.tar.gz"

for cmd in qemu-system-x86_64 gcc make curl tar git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "missing required command: $cmd"
    exit 1
  fi
done

ROOT="$(cd "$(dirname "$0")" && pwd)"
WORK="$ROOT/workdir"
mkdir -p "$WORK"

echo "This script prepares a QEMU validation workspace for Linux 6.8.y."
echo "It is intentionally conservative and may require manual follow-up."

cd "$WORK"

if [[ ! -f linux-6.8.12.tar.xz ]]; then
  curl -L "$KERNEL_URL" -o linux-6.8.12.tar.xz
fi

if [[ ! -f buildroot-2024.02.tar.gz ]]; then
  curl -L "$BUILDROOT_URL" -o buildroot-2024.02.tar.gz
fi

if [[ ! -d linux-6.8.12 ]]; then
  tar -xf linux-6.8.12.tar.xz
fi

if [[ ! -d buildroot-2024.02 ]]; then
  tar -xf buildroot-2024.02.tar.gz
fi

cd linux-6.8.12
git init >/dev/null 2>&1 || true
git config user.email "kv_deadline_scheduler@example.invalid"
git config user.name "KV Deadline Scheduler"
git add -A >/dev/null 2>&1 || true
git commit -m "linux-6.8.12 base" >/dev/null 2>&1 || true

echo "Apply patches with:"
echo "  git am \"$ROOT/../kernel_patches/mm_intent_rfc/patches\"/*.patch"
echo
echo "Use minimal config:"
echo "  cp \"$ROOT/minimal.config\" .config"
echo "  make olddefconfig"
echo "  make -j\$(nproc) bzImage"
echo
echo "Then boot with QEMU and mount debugfs to inspect /sys/kernel/debug/mm_intent"
