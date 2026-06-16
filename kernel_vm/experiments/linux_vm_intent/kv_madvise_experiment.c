#define _GNU_SOURCE
#include <errno.h>
#include <getopt.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

#ifndef MADV_COLD
#define MADV_COLD -1
#endif

#ifndef MADV_PAGEOUT
#define MADV_PAGEOUT -1
#endif

typedef struct {
    size_t total_mb;
    size_t iterations;
    size_t page_stride;
} config_t;

typedef struct {
    unsigned char *base;
    size_t len;
    const char *name;
} region_t;

static long page_size(void) {
    long value = sysconf(_SC_PAGESIZE);
    return value > 0 ? value : 4096;
}

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ((uint64_t)ts.tv_sec * 1000000000ULL) + (uint64_t)ts.tv_nsec;
}

static double us_per_region_access(region_t region, size_t stride_pages) {
    volatile unsigned char sink = 0;
    long ps = page_size();
    size_t stride = (size_t)ps * (stride_pages == 0 ? 1 : stride_pages);
    size_t page_count = 0;
    if (page_count == 0) {
        if (region.len == 0) {
            return 0.0;
        }
    }
    uint64_t start = now_ns();
    for (size_t offset = 0; offset < region.len; offset += stride) {
        sink ^= region.base[offset];
        page_count += 1;
    }
    uint64_t elapsed = now_ns() - start;
    (void)sink;
    if (page_count == 0) {
        return 0.0;
    }
    return ((double)elapsed / 1000.0) / (double)page_count;
}

static void touch_region(region_t region) {
    long ps = page_size();
    for (size_t offset = 0; offset < region.len; offset += (size_t)ps) {
        region.base[offset] = (unsigned char)(offset / (size_t)ps);
    }
}

static long read_rss_kb(void) {
    FILE *fh = fopen("/proc/self/statm", "r");
    long total_pages = 0;
    long resident_pages = 0;
    if (!fh) {
        return -1;
    }
    if (fscanf(fh, "%ld %ld", &total_pages, &resident_pages) != 2) {
        fclose(fh);
        return -1;
    }
    fclose(fh);
    return (resident_pages * page_size()) / 1024;
}

static void print_rusage_delta(struct rusage before, struct rusage after) {
    printf("Minor faults delta: %ld\n", after.ru_minflt - before.ru_minflt);
    printf("Major faults delta: %ld\n", after.ru_majflt - before.ru_majflt);
}

static int apply_madvise(region_t region, int advice, const char *label) {
    if (advice < 0) {
        printf("%s: unavailable on this build\n", label);
        return -1;
    }
    if (region.len == 0) {
        printf("%s: skipped because region is empty\n", label);
        return 0;
    }
    if (madvise(region.base, region.len, advice) != 0) {
        printf("%s: failed: %s\n", label, strerror(errno));
        return -1;
    }
    printf("%s: applied\n", label);
    return 0;
}

static void usage(const char *prog) {
    fprintf(stderr,
        "Usage: %s [--mb N] [--iterations N] [--page-stride N]\n",
        prog);
}

static config_t parse_args(int argc, char **argv) {
    config_t cfg = {
        .total_mb = 512,
        .iterations = 8,
        .page_stride = 1,
    };

    static struct option options[] = {
        {"mb", required_argument, NULL, 'm'},
        {"iterations", required_argument, NULL, 'i'},
        {"page-stride", required_argument, NULL, 's'},
        {0, 0, 0, 0},
    };

    int opt;
    while ((opt = getopt_long(argc, argv, "", options, NULL)) != -1) {
        switch (opt) {
            case 'm':
                cfg.total_mb = (size_t)strtoull(optarg, NULL, 10);
                break;
            case 'i':
                cfg.iterations = (size_t)strtoull(optarg, NULL, 10);
                break;
            case 's':
                cfg.page_stride = (size_t)strtoull(optarg, NULL, 10);
                break;
            default:
                usage(argv[0]);
                exit(2);
        }
    }
    return cfg;
}

int main(int argc, char **argv) {
    if (sysconf(_SC_PAGESIZE) <= 0) {
        fprintf(stderr, "Unable to determine page size\n");
        return 1;
    }

    config_t cfg = parse_args(argc, argv);
    size_t total_bytes = cfg.total_mb * 1024UL * 1024UL;
    size_t hot_bytes = total_bytes * 10 / 100;
    size_t warm_bytes = total_bytes * 20 / 100;
    size_t cold_bytes = total_bytes * 60 / 100;
    size_t done_bytes = total_bytes - hot_bytes - warm_bytes - cold_bytes;

    unsigned char *mapping = mmap(NULL, total_bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED) {
        fprintf(stderr, "mmap failed: %s\n", strerror(errno));
        return 1;
    }

    region_t hot = { mapping, hot_bytes, "decode-critical-hot" };
    region_t warm = { mapping + hot_bytes, warm_bytes, "warm" };
    region_t cold = { mapping + hot_bytes + warm_bytes, cold_bytes, "cold-spillable" };
    region_t done = { mapping + hot_bytes + warm_bytes + cold_bytes, done_bytes, "done-freeable" };

    printf("KV madvise experiment\n");
    printf("Total region: %zu MB\n", cfg.total_mb);
    printf("Page size: %ld bytes\n", page_size());
    printf("Page stride: %zu page(s)\n\n", cfg.page_stride);
    printf("Region layout:\n");
    printf("  hot:  %zu MB\n", hot.len / 1024 / 1024);
    printf("  warm: %zu MB\n", warm.len / 1024 / 1024);
    printf("  cold: %zu MB\n", cold.len / 1024 / 1024);
    printf("  done: %zu MB\n\n", done.len / 1024 / 1024);

    touch_region(hot);
    touch_region(warm);
    touch_region(cold);
    touch_region(done);

    long rss_before = read_rss_kb();
    double hot_before = us_per_region_access(hot, cfg.page_stride);
    double warm_before = us_per_region_access(warm, cfg.page_stride);
    double cold_before = us_per_region_access(cold, cfg.page_stride);
    double done_before = us_per_region_access(done, cfg.page_stride);

    struct rusage usage_before;
    struct rusage usage_after;
    getrusage(RUSAGE_SELF, &usage_before);

    printf("Before advice:\n");
    printf("  hot access:  %.2f us\n", hot_before);
    printf("  warm access: %.2f us\n", warm_before);
    printf("  cold access: %.2f us\n", cold_before);
    printf("  done access: %.2f us\n", done_before);
    printf("  minor faults: %ld\n", usage_before.ru_minflt);
    printf("  major faults: %ld\n", usage_before.ru_majflt);
    if (rss_before >= 0) {
        printf("  RSS: %ld MB\n", rss_before / 1024);
    } else {
        printf("  RSS: unavailable\n");
    }
    printf("\nApplied advice:\n");
    apply_madvise(hot, MADV_WILLNEED, "  hot: MADV_WILLNEED");
    apply_madvise(cold, MADV_COLD, "  cold: MADV_COLD");
    apply_madvise(cold, MADV_PAGEOUT, "  cold: MADV_PAGEOUT");
    apply_madvise(done, MADV_DONTNEED, "  done: MADV_DONTNEED");
    printf("\n");

    for (size_t i = 0; i < cfg.iterations; ++i) {
        touch_region(hot);
    }

    double hot_after = us_per_region_access(hot, cfg.page_stride);
    double warm_after = us_per_region_access(warm, cfg.page_stride);
    double cold_after = us_per_region_access(cold, cfg.page_stride);
    double done_after = us_per_region_access(done, cfg.page_stride);
    long rss_after = read_rss_kb();
    getrusage(RUSAGE_SELF, &usage_after);

    printf("After advice:\n");
    printf("  hot access:  %.2f us\n", hot_after);
    printf("  warm access: %.2f us\n", warm_after);
    printf("  cold access: %.2f us\n", cold_after);
    printf("  done access: %.2f us\n", done_after);
    printf("  minor faults delta: %ld\n", usage_after.ru_minflt - usage_before.ru_minflt);
    printf("  major faults delta: %ld\n", usage_after.ru_majflt - usage_before.ru_majflt);
    if (rss_after >= 0) {
        printf("  RSS: %ld MB\n", rss_after / 1024);
    } else {
        printf("  RSS: unavailable\n");
    }

    if (munmap(mapping, total_bytes) != 0) {
        fprintf(stderr, "munmap failed: %s\n", strerror(errno));
        return 1;
    }
    return 0;
}
