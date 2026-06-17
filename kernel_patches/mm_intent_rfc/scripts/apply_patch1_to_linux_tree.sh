#!/usr/bin/env bash
# apply_patch1_to_linux_tree.sh - Apply the memory-intent infrastructure
# to a Linux kernel tree.
#
# This is a fallback for environments where `git am` is not available.
# Preferred method: `git am patches/*.patch` from the kernel tree.
#
# usage: ./apply_patch1_to_linux_tree.sh <linux-tree>

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <linux-tree>"
  exit 1
fi

KERNEL_DIR="$1"
cd "${KERNEL_DIR}"

cat > include/linux/memory_intent.h <<'HEADER_EOF'
#ifndef _LINUX_MEMORY_INTENT_H
#define _LINUX_MEMORY_INTENT_H

#include <linux/interval_tree.h>
#include <linux/rcupdate.h>
#include <linux/seq_file.h>
#include <linux/types.h>

#define MM_INTENT_LATENCY_CRITICAL	0x1
#define MM_INTENT_RECLAIMABLE		0x2
#define MM_INTENT_PREFETCHABLE		0x4
#define MM_INTENT_RECOMPUTE_OK		0x8
#define MM_INTENT_BACKGROUND		0x10

struct memory_intent_region {
	struct interval_tree_node	node;
	pid_t				pid;
	u64				intent_flags;
	u64				deadline_ns;
	u32				priority;
	struct rcu_head			rcu;
};

#ifdef CONFIG_EXPERIMENTAL_MEMORY_INTENT
int memory_intent_register(struct memory_intent_region *region);
void memory_intent_unregister(pid_t pid, unsigned long start_vaddr);
struct memory_intent_region *
memory_intent_lookup(pid_t pid, unsigned long vaddr);
int memory_intent_dump_seq(struct seq_file *m);
int memory_intent_init_debugfs(void);
void memory_intent_exit_debugfs(void);
#else
static inline int memory_intent_register(struct memory_intent_region *region)
{
	return -ENOSYS;
}
static inline void memory_intent_unregister(pid_t pid, unsigned long start_vaddr) {}
static inline struct memory_intent_region *
memory_intent_lookup(pid_t pid, unsigned long vaddr) { return NULL; }
static inline int memory_intent_dump_seq(struct seq_file *m) { return 0; }
static inline int memory_intent_init_debugfs(void) { return 0; }
static inline void memory_intent_exit_debugfs(void) {}
#endif

#endif /* _LINUX_MEMORY_INTENT_H */
HEADER_EOF

python3 - <<'PY'
from pathlib import Path

mk = Path("mm/Makefile")
mk_text = mk.read_text()
mk_needle = "obj-$(CONFIG_USERFAULTFD) += userfaultfd.o\n"
mk_insert = mk_needle + "obj-$(CONFIG_EXPERIMENTAL_MEMORY_INTENT) += memory_intent.o\n"
if "obj-$(CONFIG_EXPERIMENTAL_MEMORY_INTENT) += memory_intent.o\n" not in mk_text:
    if mk_needle not in mk_text:
        raise SystemExit("needle not found in mm/Makefile")
    mk_text = mk_text.replace(mk_needle, mk_insert)
    mk.write_text(mk_text)

kc = Path("mm/Kconfig")
kc_text = kc.read_text()
kc_needle = 'source "mm/damon/Kconfig"\n\nendmenu\n'
kc_insert = """config EXPERIMENTAL_MEMORY_INTENT
\tbool "Experimental memory intent debugfs registry"
\tdepends on DEBUG_FS
\thelp
\t  Add a debugfs-only, observability-first memory-intent registry for
\t  research. This interface is intended for pinned-kernel experiments
\t  and does not change reclaim behavior.

\t  The interface accepts virtual-address ranges together with generic
\t  intent flags such as LATENCY_CRITICAL and RECLAIMABLE.

\t  This is RFC v0 infrastructure only. It is not a stable ABI and
\t  should not be treated as production-ready.

source "mm/damon/Kconfig"

endmenu
"""
if "config EXPERIMENTAL_MEMORY_INTENT\n" not in kc_text:
    if kc_needle not in kc_text:
        raise SystemExit("needle not found in mm/Kconfig")
    kc_text = kc_text.replace(kc_needle, kc_insert)
    kc.write_text(kc_text)
PY

cat > mm/memory_intent.c <<'SOURCE_EOF'
// SPDX-License-Identifier: GPL-2.0
/*
 * RFC v0 experimental memory-intent registry.
 *
 * Regions are stored in a global interval tree (rbtree-based) for efficient
 * range lookup.  Write-side serialization uses a single mutex; readers
 * (memory_intent_lookup) return a pointer under the same lock.
 */
#include <linux/debugfs.h>
#include <linux/init.h>
#include <linux/interval_tree.h>
#include <linux/kernel.h>
#include <linux/memory_intent.h>
#include <linux/mutex.h>
#include <linux/overflow.h>
#include <linux/pid.h>
#include <linux/sched/task.h>
#include <linux/seq_file.h>
#include <linux/slab.h>
#include <linux/uaccess.h>

#define MM_INTENT_LINE_MAX 128

static struct rb_root_cached memory_intent_root = RB_ROOT_CACHED;
static DEFINE_MUTEX(memory_intent_lock);
static struct dentry *memory_intent_dir;

int memory_intent_register(struct memory_intent_region *region)
{
	mutex_lock(&memory_intent_lock);
	interval_tree_insert(&region->node, &memory_intent_root);
	mutex_unlock(&memory_intent_lock);
	return 0;
}

void memory_intent_unregister(pid_t pid, unsigned long start_vaddr)
{
	struct memory_intent_region *region;
	struct interval_tree_node *node;

	mutex_lock(&memory_intent_lock);
	node = interval_tree_iter_first(&memory_intent_root,
					start_vaddr, start_vaddr);
	while (node) {
		region = container_of(node, struct memory_intent_region, node);
		if (region->pid == pid && region->node.start == start_vaddr) {
			interval_tree_remove(node, &memory_intent_root);
			kfree(region);
			break;
		}
		node = interval_tree_iter_next(node, start_vaddr, start_vaddr);
	}
	mutex_unlock(&memory_intent_lock);
}

struct memory_intent_region *
memory_intent_lookup(pid_t pid, unsigned long vaddr)
{
	struct memory_intent_region *region;
	struct interval_tree_node *node;

	mutex_lock(&memory_intent_lock);
	node = interval_tree_iter_first(&memory_intent_root, vaddr, vaddr);
	while (node) {
		region = container_of(node, struct memory_intent_region, node);
		if (region->pid == pid) {
			mutex_unlock(&memory_intent_lock);
			return region;
		}
		node = interval_tree_iter_next(node, vaddr, vaddr);
	}
	mutex_unlock(&memory_intent_lock);
	return NULL;
}

int memory_intent_dump_seq(struct seq_file *m)
{
	struct memory_intent_region *region;
	struct interval_tree_node *node;

	mutex_lock(&memory_intent_lock);
	node = interval_tree_iter_first(&memory_intent_root, 0, ULONG_MAX);
	while (node) {
		region = container_of(node, struct memory_intent_region, node);
		seq_printf(m, "%d 0x%lx 0x%lx 0x%llx %llu %u\n",
			   region->pid,
			   region->node.start,
			   region->node.last + 1,
			   region->intent_flags,
			   region->deadline_ns,
			   region->priority);
		node = interval_tree_iter_next(node, 0, ULONG_MAX);
	}
	mutex_unlock(&memory_intent_lock);
	return 0;
}

static void memory_intent_clear_all_locked(void)
{
	struct memory_intent_region *region;
	struct interval_tree_node *node;

	node = interval_tree_iter_first(&memory_intent_root, 0, ULONG_MAX);
	while (node) {
		region = container_of(node, struct memory_intent_region, node);
		interval_tree_remove(node, &memory_intent_root);
		kfree(region);
		node = interval_tree_iter_first(&memory_intent_root,
						0, ULONG_MAX);
	}
}

static ssize_t memory_intent_register_write(struct file *file,
					    const char __user *buffer,
					    size_t count, loff_t *ppos)
{
	char line[MM_INTENT_LINE_MAX];
	struct memory_intent_region *region;
	struct pid *pid;
	struct task_struct *task;
	pid_t pid_nr;
	unsigned int priority;
	unsigned long start;
	unsigned long length;
	unsigned long flags;
	unsigned long end;
	u64 deadline_ns;
	int parsed;

	if (!count || count >= sizeof(line))
		return -EINVAL;
	if (copy_from_user(line, buffer, count))
		return -EFAULT;
	line[count] = '\0';

	parsed = sscanf(line, "%d %lx %lx %lx %llu %u",
			&pid_nr, &start, &length, &flags,
			&deadline_ns, &priority);
	if (parsed != 6)
		return -EINVAL;
	if (!length)
		return -EINVAL;
	if (check_add_overflow(start, length, &end))
		return -EINVAL;

	pid = find_get_pid(pid_nr);
	if (!pid)
		return -ESRCH;
	task = get_pid_task(pid, PIDTYPE_PID);
	put_pid(pid);
	if (!task)
		return -ESRCH;
	put_task_struct(task);

	region = kzalloc(sizeof(*region), GFP_KERNEL);
	if (!region)
		return -ENOMEM;

	region->node.start = start;
	region->node.last = end - 1;
	region->pid = pid_nr;
	region->intent_flags = flags;
	region->deadline_ns = deadline_ns;
	region->priority = priority;

	return memory_intent_register(region) ? -ENOMEM : count;
}

static int memory_intent_dump_show(struct seq_file *m, void *v)
{
	return memory_intent_dump_seq(m);
}

static int memory_intent_dump_open(struct inode *inode, struct file *file)
{
	return single_open(file, memory_intent_dump_show, inode->i_private);
}

static ssize_t memory_intent_clear_write(struct file *file,
					 const char __user *buffer,
					 size_t count, loff_t *ppos)
{
	mutex_lock(&memory_intent_lock);
	memory_intent_clear_all_locked();
	mutex_unlock(&memory_intent_lock);
	return count;
}

static const struct file_operations memory_intent_register_fops = {
	.write = memory_intent_register_write,
	.llseek = no_llseek,
};

static const struct file_operations memory_intent_dump_fops = {
	.open = memory_intent_dump_open,
	.read = seq_read,
	.llseek = seq_lseek,
	.release = single_release,
};

static const struct file_operations memory_intent_clear_fops = {
	.write = memory_intent_clear_write,
	.llseek = no_llseek,
};

int memory_intent_init_debugfs(void)
{
	if (memory_intent_dir)
		return 0;

	memory_intent_dir = debugfs_create_dir("mm_intent", NULL);
	if (IS_ERR_OR_NULL(memory_intent_dir))
		return -ENOMEM;

	if (!debugfs_create_file("register", 0200, memory_intent_dir, NULL,
				 &memory_intent_register_fops))
		goto err;

	if (!debugfs_create_file("dump", 0400, memory_intent_dir, NULL,
				 &memory_intent_dump_fops))
		goto err;

	if (!debugfs_create_file("clear", 0200, memory_intent_dir, NULL,
				 &memory_intent_clear_fops))
		goto err;

	pr_info("memory_intent: debugfs registry initialized\n");
	return 0;
err:
	debugfs_remove_recursive(memory_intent_dir);
	memory_intent_dir = NULL;
	return -ENOMEM;
}

void memory_intent_exit_debugfs(void)
{
	mutex_lock(&memory_intent_lock);
	memory_intent_clear_all_locked();
	mutex_unlock(&memory_intent_lock);

	debugfs_remove_recursive(memory_intent_dir);
	memory_intent_dir = NULL;
}

static int __init memory_intent_init(void)
{
	return memory_intent_init_debugfs();
}

fs_initcall(memory_intent_init);
SOURCE_EOF

echo "--- Patch 0001 applied (flat copy) to ${KERNEL_DIR}"
echo "    Verify with:"
echo "      grep -n 'config EXPERIMENTAL_MEMORY_INTENT' mm/Kconfig"
echo "      grep -n 'memory_intent.o' mm/Makefile"
echo "      ls -la include/linux/memory_intent.h mm/memory_intent.c"
