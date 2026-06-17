// SPDX-License-Identifier: GPL-2.0
/*
 * kv_intent_shrinker.c
 *
 * A loadable shrinker module that accepts KV-style intent metadata from
 * userspace and uses that metadata to rank reclaim candidates. The module
 * demonstrates the kernel-side control plane shape for deadline-aware memory
 * reclaim decisions.
 *
 * The shrinker manages metadata only. It does not free userspace pages
 * directly; instead it models the selection logic that a fuller integration
 * would use before reclaim or offload.
 */

#include <linux/errno.h>
#include <linux/init.h>
#include <linux/jiffies.h>
#include <linux/kernel.h>
#include <linux/kstrtox.h>
#include <linux/ktime.h>
#include <linux/list.h>
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/rculist.h>
#include <linux/rcupdate.h>
#include <linux/seq_file.h>
#include <linux/shrinker.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/string.h>
#include <linux/uaccess.h>
#include <linux/vmalloc.h>

#define KV_PROC_DIR "kv_intent"
#define KV_PROC_REGISTER "register"
#define KV_PROC_UNREGISTER "unregister"
#define KV_PROC_STATUS "status"
#define KV_STATUS_BUFSZ 128

enum kv_priority_level {
	KV_PRIORITY_COLD = 0,
	KV_PRIORITY_WARM = 1,
	KV_PRIORITY_HOT = 2,
	KV_PRIORITY_DECODE_CRITICAL = 3,
};

struct kv_block_intent {
	struct list_head list;
	u64 object_id_hash;
	u64 deadline_us;
	u64 registered_ktime_us;
	int priority;
	bool pin_requested;
	bool recompute_ok;
	u32 size_bytes;
	struct rcu_head rcu;
};

static LIST_HEAD(kv_intent_registry);
static DEFINE_SPINLOCK(kv_intent_lock);
static struct proc_dir_entry *kv_proc_root;
static struct proc_dir_entry *kv_proc_register;
static struct proc_dir_entry *kv_proc_unregister;
static struct proc_dir_entry *kv_proc_status;

static int kv_priority_weight[] = {
	[KV_PRIORITY_COLD] = 1000,
	[KV_PRIORITY_WARM] = 500,
	[KV_PRIORITY_HOT] = 125,
	[KV_PRIORITY_DECODE_CRITICAL] = 0,
};

static u64 kv_now_us(void)
{
	return ktime_to_us(ktime_get());
}

/*
 * As requested for the design sketch, urgency rises as remaining slack falls.
 * The shrinker later filters to evictable classes, so this only reorders
 * candidates within the reclaimable set.
 */
static int kv_deadline_urgency_score(const struct kv_block_intent *intent, u64 now_us)
{
	s64 elapsed_us;
	s64 remaining_us;
	s64 raw_score;

	elapsed_us = (s64)now_us - (s64)intent->registered_ktime_us;
	remaining_us = (s64)intent->deadline_us - elapsed_us;
	raw_score = 1000 - (remaining_us / 10);
	if (raw_score < 0)
		return 0;
	if (raw_score > INT_MAX)
		return INT_MAX;
	return (int)raw_score;
}

static int kv_eviction_score(const struct kv_block_intent *intent, u64 now_us)
{
	return kv_priority_weight[intent->priority] +
	       kv_deadline_urgency_score(intent, now_us);
}

static bool kv_is_evictable(const struct kv_block_intent *intent)
{
	if (intent->priority == KV_PRIORITY_DECODE_CRITICAL &&
	    intent->pin_requested)
		return false;

	if (intent->pin_requested)
		return false;

	return intent->priority == KV_PRIORITY_COLD ||
	       intent->priority == KV_PRIORITY_WARM;
}

static void kv_free_intent_rcu(struct rcu_head *rcu)
{
	struct kv_block_intent *intent =
		container_of(rcu, struct kv_block_intent, rcu);

	kvfree(intent);
}

static struct kv_block_intent *kv_find_intent_locked(u64 object_id_hash)
{
	struct kv_block_intent *intent;

	list_for_each_entry(intent, &kv_intent_registry, list) {
		if (intent->object_id_hash == object_id_hash)
			return intent;
	}

	return NULL;
}

static ssize_t kv_register_write(struct file *file, const char __user *buffer,
				 size_t count, loff_t *ppos)
{
	char local[KV_STATUS_BUFSZ];
	struct kv_block_intent *intent;
	u64 object_id_hash;
	u64 deadline_us;
	unsigned int priority;
	unsigned int size_bytes;
	unsigned long flags;
	int parsed;

	if (count == 0 || count >= sizeof(local))
		return -EINVAL;

	if (copy_from_user(local, buffer, count))
		return -EFAULT;
	local[count] = '\0';

	parsed = sscanf(local, "%llu %llu %u %u",
			&object_id_hash, &deadline_us, &priority, &size_bytes);
	if (parsed != 4)
		return -EINVAL;

	if (priority > KV_PRIORITY_DECODE_CRITICAL || size_bytes == 0)
		return -EINVAL;

	intent = kvzalloc(sizeof(*intent), GFP_KERNEL);
	if (!intent)
		return -ENOMEM;

	INIT_LIST_HEAD(&intent->list);
	intent->object_id_hash = object_id_hash;
	intent->deadline_us = deadline_us;
	intent->registered_ktime_us = kv_now_us();
	intent->priority = priority;
	intent->pin_requested = priority == KV_PRIORITY_DECODE_CRITICAL;
	intent->recompute_ok = false;
	intent->size_bytes = size_bytes;

	spin_lock_irqsave(&kv_intent_lock, flags);
	if (kv_find_intent_locked(object_id_hash)) {
		spin_unlock_irqrestore(&kv_intent_lock, flags);
		kvfree(intent);
		return -EEXIST;
	}
	list_add_tail_rcu(&intent->list, &kv_intent_registry);
	spin_unlock_irqrestore(&kv_intent_lock, flags);

	return count;
}

static ssize_t kv_unregister_write(struct file *file, const char __user *buffer,
				   size_t count, loff_t *ppos)
{
	char local[KV_STATUS_BUFSZ];
	struct kv_block_intent *intent;
	unsigned long flags;
	u64 object_id_hash;

	if (count == 0 || count >= sizeof(local))
		return -EINVAL;

	if (copy_from_user(local, buffer, count))
		return -EFAULT;
	local[count] = '\0';

	if (kstrtoull(strim(local), 10, &object_id_hash))
		return -EINVAL;

	spin_lock_irqsave(&kv_intent_lock, flags);
	intent = kv_find_intent_locked(object_id_hash);
	if (!intent) {
		spin_unlock_irqrestore(&kv_intent_lock, flags);
		return -ENOENT;
	}
	list_del_rcu(&intent->list);
	spin_unlock_irqrestore(&kv_intent_lock, flags);

	call_rcu(&intent->rcu, kv_free_intent_rcu);
	return count;
}

static int kv_status_show(struct seq_file *m, void *v)
{
	struct kv_block_intent *intent;
	u64 now_us = kv_now_us();

	rcu_read_lock();
	list_for_each_entry_rcu(intent, &kv_intent_registry, list) {
		seq_printf(m,
			   "{\"object_id_hash\":%llu,"
			   "\"deadline_us\":%llu,"
			   "\"elapsed_us\":%llu,"
			   "\"priority\":%d,"
			   "\"pin_requested\":%s,"
			   "\"recompute_ok\":%s,"
			   "\"size_bytes\":%u,"
			   "\"eviction_score\":%d}\n",
			   intent->object_id_hash,
			   intent->deadline_us,
			   now_us - intent->registered_ktime_us,
			   intent->priority,
			   intent->pin_requested ? "true" : "false",
			   intent->recompute_ok ? "true" : "false",
			   intent->size_bytes,
			   kv_eviction_score(intent, now_us));
	}
	rcu_read_unlock();

	return 0;
}

static int kv_status_open(struct inode *inode, struct file *file)
{
	return single_open(file, kv_status_show, NULL);
}

static const struct proc_ops kv_register_ops = {
	.proc_write = kv_register_write,
};

static const struct proc_ops kv_unregister_ops = {
	.proc_write = kv_unregister_write,
};

static const struct proc_ops kv_status_ops = {
	.proc_open = kv_status_open,
	.proc_read = seq_read,
	.proc_lseek = seq_lseek,
	.proc_release = single_release,
};

static unsigned long kv_shrinker_count(struct shrinker *shrinker,
				       struct shrink_control *sc)
{
	struct kv_block_intent *intent;
	unsigned long flags;
	unsigned long count = 0;

	spin_lock_irqsave(&kv_intent_lock, flags);
	list_for_each_entry(intent, &kv_intent_registry, list) {
		if (kv_is_evictable(intent))
			count++;
	}
	spin_unlock_irqrestore(&kv_intent_lock, flags);

	return count;
}

static unsigned long kv_shrinker_scan(struct shrinker *shrinker,
				      struct shrink_control *sc)
{
	struct kv_block_intent *intent;
	struct kv_block_intent *best;
	unsigned long flags;
	unsigned long freed = 0;
	u64 now_us;

	while (freed < sc->nr_to_scan) {
		int best_score = INT_MIN;

		best = NULL;
		now_us = kv_now_us();

		spin_lock_irqsave(&kv_intent_lock, flags);
		list_for_each_entry(intent, &kv_intent_registry, list) {
			int score;

			if (!kv_is_evictable(intent))
				continue;

			score = kv_eviction_score(intent, now_us);
			if (!best || score > best_score) {
				best = intent;
				best_score = score;
			}
		}

		if (!best) {
			spin_unlock_irqrestore(&kv_intent_lock, flags);
			break;
		}

		list_del_rcu(&best->list);
		spin_unlock_irqrestore(&kv_intent_lock, flags);

		call_rcu(&best->rcu, kv_free_intent_rcu);
		freed++;
	}

	return freed;
}

static struct shrinker kv_intent_shrinker = {
	.count_objects = kv_shrinker_count,
	.scan_objects = kv_shrinker_scan,
	.seeks = DEFAULT_SEEKS,
	.batch = 0,
};

static void kv_free_all_intents(void)
{
	struct kv_block_intent *intent;
	struct kv_block_intent *tmp;
	unsigned long flags;

	spin_lock_irqsave(&kv_intent_lock, flags);
	list_for_each_entry_safe(intent, tmp, &kv_intent_registry, list) {
		list_del_rcu(&intent->list);
		kvfree(intent);
	}
	spin_unlock_irqrestore(&kv_intent_lock, flags);
}

static int __init kv_intent_init(void)
{
	int ret;

	kv_proc_root = proc_mkdir(KV_PROC_DIR, NULL);
	if (!kv_proc_root)
		return -ENOMEM;

	kv_proc_register = proc_create(KV_PROC_REGISTER, 0200, kv_proc_root,
				       &kv_register_ops);
	if (!kv_proc_register) {
		ret = -ENOMEM;
		goto err_remove_root;
	}

	kv_proc_unregister = proc_create(KV_PROC_UNREGISTER, 0200, kv_proc_root,
					 &kv_unregister_ops);
	if (!kv_proc_unregister) {
		ret = -ENOMEM;
		goto err_remove_register;
	}

	kv_proc_status = proc_create(KV_PROC_STATUS, 0444, kv_proc_root,
				     &kv_status_ops);
	if (!kv_proc_status) {
		ret = -ENOMEM;
		goto err_remove_unregister;
	}

	ret = register_shrinker(&kv_intent_shrinker, "kv_intent_shrinker");
	if (ret)
		goto err_remove_status;

	pr_info("kv_intent_shrinker loaded\n");
	return 0;

err_remove_status:
	remove_proc_entry(KV_PROC_STATUS, kv_proc_root);
err_remove_unregister:
	remove_proc_entry(KV_PROC_UNREGISTER, kv_proc_root);
err_remove_register:
	remove_proc_entry(KV_PROC_REGISTER, kv_proc_root);
err_remove_root:
	remove_proc_entry(KV_PROC_DIR, NULL);
	return ret;
}

static void __exit kv_intent_exit(void)
{
	unregister_shrinker(&kv_intent_shrinker);
	if (kv_proc_status)
		remove_proc_entry(KV_PROC_STATUS, kv_proc_root);
	if (kv_proc_unregister)
		remove_proc_entry(KV_PROC_UNREGISTER, kv_proc_root);
	if (kv_proc_register)
		remove_proc_entry(KV_PROC_REGISTER, kv_proc_root);
	if (kv_proc_root)
		remove_proc_entry(KV_PROC_DIR, NULL);
	kv_free_all_intents();
	synchronize_rcu();
	pr_info("kv_intent_shrinker unloaded\n");
}

module_init(kv_intent_init);
module_exit(kv_intent_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Manish Klach");
MODULE_DESCRIPTION("Deadline-aware KV intent shrinker prototype");
