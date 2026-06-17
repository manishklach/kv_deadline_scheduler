#!/bin/bash
set -e

cd "$(dirname "$0")/experiments/linux_vm_intent"
gcc -O2 -Wall -Wextra kv_madvise_experiment.c -o kv_madvise -lpthread
./kv_madvise

cd ../userfaultfd_kv
gcc -O2 -Wall -Wextra kv_uffd_migration.c -o kv_uffd_migration -lpthread
./kv_uffd_migration

cd ../../../experiments/perf_kv
gcc -O2 -Wall -Wextra kv_perf_counters.c -o kv_perf_counters -lpthread
./kv_perf_counters

cd ../io_uring_kv
python3 kv_io_uring_prefetch.py

echo "All non-privileged experiments complete."
echo "For DAMON: sudo python3 kernel_vm/experiments/damon_kv_hotness/kv_damon_controller.py"
echo "For THP:   gcc -O2 -Wall -Wextra kernel_vm/experiments/thp_kv/kv_thp_alloc.c -o kernel_vm/experiments/thp_kv/kv_thp_alloc -lpthread && ./kernel_vm/experiments/thp_kv/kv_thp_alloc"
