/* SPDX-License-Identifier: GPL-2.0 */
#undef TRACE_SYSTEM
#define TRACE_SYSTEM kv_intent

#if !defined(_TRACE_KV_DAMON_SCHEME_H) || defined(TRACE_HEADER_MULTI_READ)
#define _TRACE_KV_DAMON_SCHEME_H

#include <linux/tracepoint.h>

TRACE_EVENT(kv_intent_classified,
	TP_PROTO(unsigned long start, unsigned long end,
		 unsigned int nr_accesses, int priority),
	TP_ARGS(start, end, nr_accesses, priority),
	TP_STRUCT__entry(
		__field(unsigned long, start)
		__field(unsigned long, end)
		__field(unsigned int, nr_accesses)
		__field(int, priority)
	),
	TP_fast_assign(
		__entry->start = start;
		__entry->end = end;
		__entry->nr_accesses = nr_accesses;
		__entry->priority = priority;
	),
	TP_printk("kv_intent: [%lx-%lx] nr_acc=%u priority=%d",
		  __entry->start, __entry->end,
		  __entry->nr_accesses, __entry->priority)
);

#endif /* _TRACE_KV_DAMON_SCHEME_H */

#undef TRACE_INCLUDE_PATH
#define TRACE_INCLUDE_PATH .
#undef TRACE_INCLUDE_FILE
#define TRACE_INCLUDE_FILE kv_damon_scheme

#include <trace/define_trace.h>
