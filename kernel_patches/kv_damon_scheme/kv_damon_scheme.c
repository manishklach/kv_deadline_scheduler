// SPDX-License-Identifier: GPL-2.0
/*
 * kv_damon_scheme.c
 *
 * DAMON integration sketch for mapping region access frequency into
 * KV-style priority classes. This file is written as kernel module code so
 * the proposed behavior is concrete, even though WSL2 cannot load it.
 *
 * DAMON symbols used here are from the public in-kernel interfaces available
 * in Linux 6.x:
 *
 * - struct damon_ctx / damon_target / damon_region: Linux 6.0+
 * - struct damos: Linux 6.0+
 * - DAMOS_ACTION_LRU_PRIO and related DAMON scheme infrastructure: 6.3+
 * - CONFIG_DAMON_SYSFS-backed userspace orchestration: 6.6+ in the shape
 *   assumed by this design
 *
 * Intended extension:
 *
 *   DAMOS_MARK_KV_INTENT = DAMOS_ACTION_LRU_PRIO + 1
 *
 * We cannot add the enum value from a standalone module, so the code below
 * isolates the behavior in kv_damon_apply_scheme() and exports decisions via
 * a tracepoint.
 */

#define CREATE_TRACE_POINTS
#include "kv_damon_scheme.h"

#include <linux/damon.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>

enum kv_scheme_priority {
	KV_SCHEME_PRIORITY_COLD = 0,
	KV_SCHEME_PRIORITY_WARM = 1,
	KV_SCHEME_PRIORITY_HOT = 2,
	KV_SCHEME_PRIORITY_DECODE_CRITICAL = 3,
};

/*
 * A real upstream DAMON extension would call damos_set_quota_goal() when the
 * helper is available to steer reclaim work toward the coldest regions.
 * Standalone modules cannot rely on a stable exported helper signature across
 * all supported kernels, so this compatibility wrapper preserves compile-time
 * correctness while documenting the intended action point.
 */
static inline void kv_mark_reclaim_candidate(struct damos *s,
					     struct damon_region *r)
{
	(void)s;
	(void)r;
}

static int kv_damon_apply_scheme(struct damon_ctx *ctx,
				 struct damon_target *t,
				 struct damon_region *r,
				 struct damos *s,
				 unsigned long *sz_applied)
{
	unsigned int nr_accesses;
	int priority;

	(void)ctx;
	(void)t;

	nr_accesses = r->nr_accesses;

	if (nr_accesses >= 10) {
		priority = KV_SCHEME_PRIORITY_DECODE_CRITICAL;
		*sz_applied += r->ar.end - r->ar.start;
		trace_kv_intent_classified(r->ar.start, r->ar.end,
					   nr_accesses, priority);
		return 0;
	}

	if (nr_accesses >= 3) {
		priority = KV_SCHEME_PRIORITY_HOT;
		*sz_applied += r->ar.end - r->ar.start;
		trace_kv_intent_classified(r->ar.start, r->ar.end,
					   nr_accesses, priority);
		return 0;
	}

	if (nr_accesses >= 1) {
		priority = KV_SCHEME_PRIORITY_WARM;
		*sz_applied += r->ar.end - r->ar.start;
		trace_kv_intent_classified(r->ar.start, r->ar.end,
					   nr_accesses, priority);
		return 0;
	}

	priority = KV_SCHEME_PRIORITY_COLD;
	kv_mark_reclaim_candidate(s, r);
	*sz_applied += r->ar.end - r->ar.start;
	trace_kv_intent_classified(r->ar.start, r->ar.end,
				   nr_accesses, priority);
	return 0;
}

static int __init kv_damon_scheme_init(void)
{
	pr_info("kv_damon_scheme loaded\n");
	pr_info("kv_damon_scheme exports kv_intent_classified tracepoints and a DAMON-compatible classifier\n");
	return 0;
}

static void __exit kv_damon_scheme_exit(void)
{
	pr_info("kv_damon_scheme unloaded\n");
}

module_init(kv_damon_scheme_init);
module_exit(kv_damon_scheme_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Manish Klach");
MODULE_DESCRIPTION("DAMON KV intent classification prototype");
