#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/userfaultfd.h>
#include <poll.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define MB (1024UL * 1024UL)
#define HBM_SIZE (64UL * MB)
#define DRAM_SIZE (256UL * MB)
#define BLOCK_SIZE (4UL * MB)
#define NUM_BLOCKS 16
#define DECODE_STEPS 256

struct context {
    int uffd;
    size_t page_size;
    uint8_t *hbm_region;
    uint8_t *dram_region;
    uint64_t latencies_us[DECODE_STEPS];
    uint8_t block_migrated[NUM_BLOCKS];
    size_t latency_count;
    size_t migration_count;
    int done;
};

static uint64_t now_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t) ts.tv_sec * 1000000ULL + (uint64_t) ts.tv_nsec / 1000ULL;
}

static int cmp_u64(const void *left, const void *right) {
    const uint64_t a = *(const uint64_t *) left;
    const uint64_t b = *(const uint64_t *) right;
    if (a < b) {
        return -1;
    }
    if (a > b) {
        return 1;
    }
    return 0;
}

static uint64_t percentile(uint64_t *values, size_t count, double pct) {
    if (count == 0) {
        return 0;
    }
    qsort(values, count, sizeof(uint64_t), cmp_u64);
    size_t index = (size_t) ((pct / 100.0) * (double) (count - 1));
    return values[index];
}

static void write_results(struct context *ctx) {
    char path[256];
    snprintf(path, sizeof(path), "%s", "results/uffd_migration_result.json");
    (void) mkdir("results", 0755);
    FILE *out = fopen(path, "w");
    if (out == NULL) {
        perror("fopen");
        return;
    }
    uint64_t tmp[DECODE_STEPS];
    memcpy(tmp, ctx->latencies_us, ctx->latency_count * sizeof(uint64_t));
    fprintf(out, "{\n");
    fprintf(out, "  \"total_migrations\": %zu,\n", ctx->migration_count);
    fprintf(out, "  \"blocks_migrated\": %u,\n", NUM_BLOCKS);
    fprintf(out, "  \"p50_us\": %" PRIu64 ",\n", percentile(tmp, ctx->latency_count, 50.0));
    memcpy(tmp, ctx->latencies_us, ctx->latency_count * sizeof(uint64_t));
    fprintf(out, "  \"p95_us\": %" PRIu64 ",\n", percentile(tmp, ctx->latency_count, 95.0));
    memcpy(tmp, ctx->latencies_us, ctx->latency_count * sizeof(uint64_t));
    fprintf(out, "  \"p99_us\": %" PRIu64 ",\n", percentile(tmp, ctx->latency_count, 99.0));
    fprintf(out, "  \"note\": \"Each logical KV block is represented by the first page of a 4MB region. This is a block-level migration proxy, not full-page-set migration.\"\n");
    fprintf(out, "}\n");
    fclose(out);
}

static void *fault_handler(void *arg) {
    struct context *ctx = (struct context *) arg;
    struct pollfd pfd = {.fd = ctx->uffd, .events = POLLIN};

    while (!ctx->done) {
        int poll_result = poll(&pfd, 1, 100);
        if (poll_result <= 0) {
            continue;
        }

        struct uffd_msg msg;
        ssize_t read_bytes = read(ctx->uffd, &msg, sizeof(msg));
        if (read_bytes <= 0) {
            continue;
        }
        if (msg.event != UFFD_EVENT_PAGEFAULT) {
            continue;
        }

        uint64_t start_us = now_us();
        uintptr_t fault_addr = (uintptr_t) msg.arg.pagefault.address;
        uintptr_t page_addr = fault_addr & ~(ctx->page_size - 1);
        size_t block_index = (page_addr - (uintptr_t) ctx->hbm_region) / BLOCK_SIZE;
        size_t page_offset = page_addr - (uintptr_t) ctx->hbm_region;

        struct uffdio_copy copy;
        memset(&copy, 0, sizeof(copy));
        copy.src = (unsigned long) (ctx->dram_region + page_offset);
        copy.dst = (unsigned long) page_addr;
        copy.len = ctx->page_size;
        if (ioctl(ctx->uffd, UFFDIO_COPY, &copy) == -1) {
            perror("UFFDIO_COPY");
            continue;
        }

        uint64_t end_us = now_us();
        if (ctx->latency_count < DECODE_STEPS) {
            ctx->latencies_us[ctx->latency_count++] = end_us - start_us;
        }
        if (block_index < NUM_BLOCKS) {
            ctx->block_migrated[block_index] = 1;
        }
        ctx->migration_count++;
        if (ctx->migration_count <= 16) {
            printf(
                "fault addr=0x%lx block=%zu latency=%" PRIu64 "us\n",
                (unsigned long) fault_addr,
                block_index,
                end_us - start_us
            );
        }
    }
    return NULL;
}

static int setup_userfaultfd(struct context *ctx) {
    ctx->uffd = (int) syscall(SYS_userfaultfd, O_CLOEXEC | O_NONBLOCK);
    if (ctx->uffd == -1) {
        perror("userfaultfd");
        return -1;
    }

    struct uffdio_api api;
    memset(&api, 0, sizeof(api));
    api.api = UFFD_API;
    if (ioctl(ctx->uffd, UFFDIO_API, &api) == -1) {
        perror("UFFDIO_API");
        return -1;
    }

    struct uffdio_register reg;
    memset(&reg, 0, sizeof(reg));
    reg.range.start = (unsigned long) ctx->hbm_region;
    reg.range.len = HBM_SIZE;
    reg.mode = UFFDIO_REGISTER_MODE_MISSING;
    if (ioctl(ctx->uffd, UFFDIO_REGISTER, &reg) == -1) {
        perror("UFFDIO_REGISTER");
        return -1;
    }
    return 0;
}

int main(void) {
    struct context ctx;
    memset(&ctx, 0, sizeof(ctx));
    ctx.page_size = (size_t) sysconf(_SC_PAGESIZE);
    ctx.hbm_region = mmap(NULL, HBM_SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    ctx.dram_region = mmap(NULL, DRAM_SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (ctx.hbm_region == MAP_FAILED || ctx.dram_region == MAP_FAILED) {
        perror("mmap");
        return 1;
    }

    for (size_t offset = 0; offset < HBM_SIZE; offset += ctx.page_size) {
        ctx.dram_region[offset] = (uint8_t) ((offset / ctx.page_size) & 0xFF);
    }

    if (setup_userfaultfd(&ctx) != 0) {
        return 1;
    }

    pthread_t handler;
    if (pthread_create(&handler, NULL, fault_handler, &ctx) != 0) {
        perror("pthread_create");
        return 1;
    }

    srand(42);
    for (size_t step = 0; step < DECODE_STEPS; ++step) {
        size_t block = (size_t) (rand() % NUM_BLOCKS);
        size_t offset = block * BLOCK_SIZE;
        volatile uint8_t value = ctx.hbm_region[offset];
        (void) value;
    }

    ctx.done = 1;
    pthread_join(handler, NULL);

    size_t migrated_blocks = 0;
    for (size_t i = 0; i < NUM_BLOCKS; ++i) {
        migrated_blocks += ctx.block_migrated[i] ? 1U : 0U;
    }

    uint64_t tmp[DECODE_STEPS];
    memcpy(tmp, ctx.latencies_us, ctx.latency_count * sizeof(uint64_t));
    uint64_t p50 = percentile(tmp, ctx.latency_count, 50.0);
    memcpy(tmp, ctx.latencies_us, ctx.latency_count * sizeof(uint64_t));
    uint64_t p95 = percentile(tmp, ctx.latency_count, 95.0);
    memcpy(tmp, ctx.latencies_us, ctx.latency_count * sizeof(uint64_t));
    uint64_t p99 = percentile(tmp, ctx.latency_count, 99.0);

    printf("Total migrations: %zu\n", ctx.migration_count);
    printf("p50 migration latency: %" PRIu64 " us\n", p50);
    printf("p95 migration latency: %" PRIu64 " us\n", p95);
    printf("p99 migration latency: %" PRIu64 " us\n", p99);
    printf("Blocks migrated: %zu/%d\n", migrated_blocks, NUM_BLOCKS);

    write_results(&ctx);
    munmap(ctx.hbm_region, HBM_SIZE);
    munmap(ctx.dram_region, DRAM_SIZE);
    close(ctx.uffd);
    return 0;
}
