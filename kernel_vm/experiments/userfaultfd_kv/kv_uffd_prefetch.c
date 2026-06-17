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
#define BLOCK_SIZE (4UL * MB)
#define NUM_BLOCKS 16
#define DECODE_STEPS 256

struct context {
    int uffd;
    size_t page_size;
    uint8_t *hbm_region;
    uint8_t *dram_region;
    uint8_t block_present[NUM_BLOCKS];
    size_t fault_count;
};

static void write_results(size_t fault_count, double hit_rate) {
    (void) mkdir("results", 0755);
    FILE *out = fopen("results/uffd_prefetch_result.json", "w");
    if (out == NULL) {
        perror("fopen");
        return;
    }
    fprintf(out, "{\n");
    fprintf(out, "  \"reactive_faults\": %zu,\n", fault_count);
    fprintf(out, "  \"prefetch_hit_rate_pct\": %.2f,\n", hit_rate);
    fprintf(out, "  \"note\": \"Prefetch copies the first page of each predicted 4MB logical block as a block-level proxy.\"\n");
    fprintf(out, "}\n");
    fclose(out);
}

static int copy_page(struct context *ctx, uintptr_t page_addr) {
    size_t page_offset = page_addr - (uintptr_t) ctx->hbm_region;
    struct uffdio_copy copy;
    memset(&copy, 0, sizeof(copy));
    copy.src = (unsigned long) (ctx->dram_region + page_offset);
    copy.dst = (unsigned long) page_addr;
    copy.len = ctx->page_size;
    return ioctl(ctx->uffd, UFFDIO_COPY, &copy);
}

static void *fault_handler(void *arg) {
    struct context *ctx = (struct context *) arg;
    struct pollfd pfd = {.fd = ctx->uffd, .events = POLLIN};

    while (1) {
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
        uintptr_t page_addr = (uintptr_t) msg.arg.pagefault.address & ~(ctx->page_size - 1);
        size_t block = (page_addr - (uintptr_t) ctx->hbm_region) / BLOCK_SIZE;
        if (copy_page(ctx, page_addr) == -1) {
            perror("UFFDIO_COPY");
            continue;
        }
        if (block < NUM_BLOCKS) {
            ctx->block_present[block] = 1;
        }
        ctx->fault_count++;
    }
    return NULL;
}

static int setup_uffd(struct context *ctx) {
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
    ctx.dram_region = mmap(NULL, HBM_SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (ctx.hbm_region == MAP_FAILED || ctx.dram_region == MAP_FAILED) {
        perror("mmap");
        return 1;
    }
    for (size_t offset = 0; offset < HBM_SIZE; offset += ctx.page_size) {
        ctx.dram_region[offset] = (uint8_t) ((offset / ctx.page_size) & 0xFF);
    }
    if (setup_uffd(&ctx) != 0) {
        return 1;
    }
    pthread_t handler;
    if (pthread_create(&handler, NULL, fault_handler, &ctx) != 0) {
        perror("pthread_create");
        return 1;
    }

    srand(42);
    size_t prefetch_hits = 0;
    size_t prefetch_attempts = 0;
    size_t last_block = 0;
    for (size_t step = 0; step < DECODE_STEPS; ++step) {
        size_t predicted = (last_block + 1) % NUM_BLOCKS;
        prefetch_attempts++;
        if (ctx.block_present[predicted]) {
            prefetch_hits++;
        } else {
            uintptr_t page_addr = (uintptr_t) ctx.hbm_region + predicted * BLOCK_SIZE;
            if (copy_page(&ctx, page_addr) == -1 && errno != EEXIST) {
                perror("prefetch UFFDIO_COPY");
            }
            ctx.block_present[predicted] = 1;
        }

        size_t block = (last_block + (size_t) (rand() % 3)) % NUM_BLOCKS;
        last_block = block;
        volatile uint8_t value = ctx.hbm_region[block * BLOCK_SIZE];
        (void) value;
    }

    double hit_rate = prefetch_attempts == 0 ? 0.0 : (100.0 * (double) prefetch_hits / (double) prefetch_attempts);
    printf("Reactive faults: %zu\n", ctx.fault_count);
    printf("Prefetch hit rate: %.2f%%\n", hit_rate);
    printf("This experiment models proactive KV block migration before the next decode-like step.\n");
    write_results(ctx.fault_count, hit_rate);
    return 0;
}
