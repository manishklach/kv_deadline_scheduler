#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <linux-build-dir>"
  exit 1
fi

KERNEL_DIR="$1"
WORK_ROOT="${WORK_ROOT:-/tmp/kvds-kernel}"
INITRAMFS_ROOT="${WORK_ROOT}/initramfs-smoke"
INITRAMFS_GZ="${WORK_ROOT}/initramfs-smoke.cpio.gz"
BZIMAGE="${KERNEL_DIR}/arch/x86/boot/bzImage"

if [[ ! -f "${BZIMAGE}" ]]; then
  echo "missing bzImage: ${BZIMAGE}"
  exit 1
fi

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo "missing qemu-system-x86_64"
  exit 1
fi

mkdir -p "${WORK_ROOT}"
rm -rf "${INITRAMFS_ROOT}"
mkdir -p \
  "${INITRAMFS_ROOT}/bin" \
  "${INITRAMFS_ROOT}/usr/bin" \
  "${INITRAMFS_ROOT}/lib/x86_64-linux-gnu" \
  "${INITRAMFS_ROOT}/lib64" \
  "${INITRAMFS_ROOT}/proc" \
  "${INITRAMFS_ROOT}/sys/kernel/debug" \
  "${INITRAMFS_ROOT}/dev"

cp /bin/bash "${INITRAMFS_ROOT}/bin/"
cp /usr/bin/mount "${INITRAMFS_ROOT}/usr/bin/"
cp /usr/bin/cat "${INITRAMFS_ROOT}/usr/bin/"
cp /lib/x86_64-linux-gnu/libtinfo.so.6 "${INITRAMFS_ROOT}/lib/x86_64-linux-gnu/"
cp /lib/x86_64-linux-gnu/libc.so.6 "${INITRAMFS_ROOT}/lib/x86_64-linux-gnu/"
cp /lib/x86_64-linux-gnu/libmount.so.1 "${INITRAMFS_ROOT}/lib/x86_64-linux-gnu/"
cp /lib/x86_64-linux-gnu/libselinux.so.1 "${INITRAMFS_ROOT}/lib/x86_64-linux-gnu/"
cp /lib/x86_64-linux-gnu/libblkid.so.1 "${INITRAMFS_ROOT}/lib/x86_64-linux-gnu/"
cp /lib/x86_64-linux-gnu/libpcre2-8.so.0 "${INITRAMFS_ROOT}/lib/x86_64-linux-gnu/"
cp /lib64/ld-linux-x86-64.so.2 "${INITRAMFS_ROOT}/lib64/"

cat > "${INITRAMFS_ROOT}/init" <<'EOF'
#!/bin/bash
export PATH=/bin:/usr/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev || true
mount -t debugfs debugfs /sys/kernel/debug
printf 'mm_intent boot ok\n'
printf '%s 0x100000 0x2000 0x1 1000000 90\n' "$$" > /sys/kernel/debug/mm_intent/register
printf 'mm_intent dump begin\n'
cat /sys/kernel/debug/mm_intent/dump
printf 'mm_intent dump end\n'
printf 'b' > /proc/sysrq-trigger
EOF
chmod +x "${INITRAMFS_ROOT}/init"

mknod -m 600 "${INITRAMFS_ROOT}/dev/console" c 5 1
mknod -m 666 "${INITRAMFS_ROOT}/dev/null" c 1 3

(
  cd "${INITRAMFS_ROOT}"
  find . -print0 | cpio --null -ov --format=newc 2>/dev/null | gzip -9 > "${INITRAMFS_GZ}"
)

timeout 120s qemu-system-x86_64 \
  -accel tcg \
  -m 2048 \
  -kernel "${BZIMAGE}" \
  -initrd "${INITRAMFS_GZ}" \
  -append "console=ttyS0 rdinit=/init nokaslr" \
  -nographic \
  -no-reboot
