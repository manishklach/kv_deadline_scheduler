#define _GNU_SOURCE

#include <asm/unistd.h>
#include <inttypes.h>
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define MB (1024UL * 1024UL)
#define REGION_SIZE (256UL * MB)

struct pattern_result {
    uint64_t instructions;
    uint64_t cache_refs;
    uint64_t cache_misses;
    double miss_rate;
};

static long perf_open(struct perf_event_attr *hw_event) {
    return syscall(__NR_perf_event_open, hw_event, 0, -1, -1, 0);
}

static int open_counter(uint64_t config) {
    struct perf_event_attr attr;
    memset(&attr, 0, sizeof(attr));
    attr.type = PERF_TYPE_HARDWARE;
    attr.size = sizeof(attr);
    attr.config = config;
    attr.disabled = 1;
    attr.exclude_kernel = 1;
    attr.exclude_hv = 1;
    return (int) perf_open(&attr);
}

static uint64_t run_pattern(uint8_t *region, size_t size, const char *pattern) {
    volatile uint8_t sink = 0;
    if (strcmp(pattern, "sequential") == 0) {
        for (size_t offset = 0; offset < size; offset += 64) {
            sink ^= region[offset];
        }
    } else if (strcmp(pattern, "kv-random") == 0) {
        for (int iter = 0; iter < 100000; ++iter) {
            size_t offset = ((size_t) rand() % 64UL) * (4UL * MB);
            sink ^= region[offset % size];
        }
    } else {
        madvise(region, size, MADV_COLD);
        for (size_t offset = 0; offset < size; offset += 4096) {
            sink ^= region[offset];
        }
    }
    return sink;
}

static uint64_t read_counter(int fd) {
    uint64_t value = 0;
    if (read(fd, &value, sizeof(value)) != sizeof(value)) {
        return 0;
    }
    return value;
}

static struct pattern_result measure_pattern(const char *label, uint8_t *region, size_t size) {
    struct pattern_result result;
    memset(&result, 0, sizeof(result));
    int misses = open_counter(PERF_COUNT_HW_CACHE_MISSES);
    int refs = open_counter(PERF_COUNT_HW_CACHE_REFERENCES);
    int instructions = open_counter(PERF_COUNT_HW_INSTRUCTIONS);
    if (misses < 0 || refs < 0 || instructions < 0) {
        perror("perf_event_open");
        exit(1);
    }

    ioctl(misses, PERF_EVENT_IOC_RESET, 0);
    ioctl(refs, PERF_EVENT_IOC_RESET, 0);
    ioctl(instructions, PERF_EVENT_IOC_RESET, 0);
    ioctl(misses, PERF_EVENT_IOC_ENABLE, 0);
    ioctl(refs, PERF_EVENT_IOC_ENABLE, 0);
    ioctl(instructions, PERF_EVENT_IOC_ENABLE, 0);

    run_pattern(region, size, label);

    ioctl(misses, PERF_EVENT_IOC_DISABLE, 0);
    ioctl(refs, PERF_EVENT_IOC_DISABLE, 0);
    ioctl(instructions, PERF_EVENT_IOC_DISABLE, 0);

    result.cache_misses = read_counter(misses);
    result.cache_refs = read_counter(refs);
    result.instructions = read_counter(instructions);
    result.miss_rate = result.cache_refs == 0 ? 0.0 : (100.0 * (double) result.cache_misses / (double) result.cache_refs);
    printf(
        "%-12s | %-12" PRIu64 " | %-10" PRIu64 " | %-12" PRIu64 " | %6.2f%%\n",
        label,
        result.instructions,
        result.cache_refs,
        result.cache_misses,
        result.miss_rate
    );

    close(misses);
    close(refs);
    close(instructions);
    return result;
}

int main(void) {
    srand(42);
    uint8_t *region = mmap(NULL, REGION_SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (region == MAP_FAILED) {
        perror("mmap");
        return 1;
    }
    for (size_t offset = 0; offset < REGION_SIZE; offset += 4096) {
        region[offset] = (uint8_t) ((offset / 4096) & 0xFF);
    }

    printf("Pattern      | Instructions | Cache refs | Cache misses | Miss rate\n");
    struct pattern_result sequential = measure_pattern("sequential", region, REGION_SIZE);
    struct pattern_result kv_random = measure_pattern("kv-random", region, REGION_SIZE);
    struct pattern_result evicted_kv = measure_pattern("evicted-kv", region, REGION_SIZE);

    (void) mkdir("results", 0755);
    FILE *out = fopen("results/perf_result.json", "w");
    if (out != NULL) {
        fprintf(out, "{\n");
        fprintf(out, "  \"sequential\": {\n");
        fprintf(out, "    \"instructions\": %" PRIu64 ",\n", sequential.instructions);
        fprintf(out, "    \"cache_refs\": %" PRIu64 ",\n", sequential.cache_refs);
        fprintf(out, "    \"cache_misses\": %" PRIu64 ",\n", sequential.cache_misses);
        fprintf(out, "    \"miss_rate_pct\": %.2f\n", sequential.miss_rate);
        fprintf(out, "  },\n");
        fprintf(out, "  \"kv_random\": {\n");
        fprintf(out, "    \"instructions\": %" PRIu64 ",\n", kv_random.instructions);
        fprintf(out, "    \"cache_refs\": %" PRIu64 ",\n", kv_random.cache_refs);
        fprintf(out, "    \"cache_misses\": %" PRIu64 ",\n", kv_random.cache_misses);
        fprintf(out, "    \"miss_rate_pct\": %.2f\n", kv_random.miss_rate);
        fprintf(out, "  },\n");
        fprintf(out, "  \"evicted_kv\": {\n");
        fprintf(out, "    \"instructions\": %" PRIu64 ",\n", evicted_kv.instructions);
        fprintf(out, "    \"cache_refs\": %" PRIu64 ",\n", evicted_kv.cache_refs);
        fprintf(out, "    \"cache_misses\": %" PRIu64 ",\n", evicted_kv.cache_misses);
        fprintf(out, "    \"miss_rate_pct\": %.2f\n", evicted_kv.miss_rate);
        fprintf(out, "  },\n");
        fprintf(out, "  \"note\": \"perf_event_open counters reflect userspace cache behavior, not GPU HBM control.\"\n");
        fprintf(out, "}\n");
        fclose(out);
    }
    munmap(region, REGION_SIZE);
    return 0;
}
