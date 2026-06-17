#define _GNU_SOURCE

#include <inttypes.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define MB (1024UL * 1024UL)
#define REGION_SIZE (512UL * MB)
#define RANDOM_READS 10000
#define SEQ_READS 10000

static double elapsed_sec(struct timespec start, struct timespec end) {
    return (double) (end.tv_sec - start.tv_sec) + (double) (end.tv_nsec - start.tv_nsec) / 1e9;
}

static void prefault(uint8_t *region, size_t size, size_t stride) {
    for (size_t offset = 0; offset < size; offset += stride) {
        region[offset] = (uint8_t) (offset / stride);
    }
}

static double run_seq(uint8_t *region, size_t size) {
    volatile uint8_t sink = 0;
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int iter = 0; iter < SEQ_READS; ++iter) {
        size_t offset = (size_t) iter * 64 % size;
        sink ^= region[offset];
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    return ((double) SEQ_READS * 64.0 / (1024.0 * 1024.0)) / elapsed_sec(start, end);
}

static double run_random(uint8_t *region, size_t size) {
    volatile uint8_t sink = 0;
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int iter = 0; iter < RANDOM_READS; ++iter) {
        size_t offset = ((size_t) rand() * 4096UL) % size;
        sink ^= region[offset];
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    return ((double) RANDOM_READS / 1000000.0) / elapsed_sec(start, end);
}

static long read_anon_huge_pages_kb(void) {
    FILE *fp = fopen("/proc/self/status", "r");
    if (fp == NULL) {
        return -1;
    }
    char line[256];
    long value = -1;
    while (fgets(line, sizeof(line), fp) != NULL) {
        if (strncmp(line, "HugetlbPages:", 13) == 0 || strncmp(line, "RssAnon:", 8) == 0) {
            continue;
        }
        if (strncmp(line, "VmSwap:", 7) == 0) {
            continue;
        }
    }
    fclose(fp);
    return value;
}

int main(void) {
    srand(42);
    uint8_t *normal = mmap(NULL, REGION_SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    uint8_t *thp = mmap(NULL, REGION_SIZE, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (normal == MAP_FAILED || thp == MAP_FAILED) {
        perror("mmap");
        return 1;
    }
    if (madvise(thp, REGION_SIZE, MADV_HUGEPAGE) != 0) {
        perror("madvise MADV_HUGEPAGE");
    }

    prefault(normal, REGION_SIZE, 4096);
    prefault(thp, REGION_SIZE, 4096);

    double seq_normal = run_seq(normal, REGION_SIZE);
    double seq_thp = run_seq(thp, REGION_SIZE);
    double rand_normal = run_random(normal, REGION_SIZE);
    double rand_thp = run_random(thp, REGION_SIZE);

    printf("Page size    | Sequential MB/s | Random MPPS | TLB miss indicator\n");
    printf("4KB pages    | %10.2f | %11.4f | baseline\n", seq_normal, rand_normal);
    printf("2MB THP      | %10.2f | %11.4f | relative\n", seq_thp, rand_thp);

    (void) mkdir("results", 0755);
    FILE *out = fopen("results/thp_alloc_result.json", "w");
    if (out != NULL) {
        fprintf(out, "{\n");
        fprintf(out, "  \"seq_normal_mb_s\": %.2f,\n", seq_normal);
        fprintf(out, "  \"seq_thp_mb_s\": %.2f,\n", seq_thp);
        fprintf(out, "  \"random_normal_mpps\": %.4f,\n", rand_normal);
        fprintf(out, "  \"random_thp_mpps\": %.4f,\n", rand_thp);
        fprintf(out, "  \"anon_huge_pages_kb\": %ld\n", read_anon_huge_pages_kb());
        fprintf(out, "}\n");
        fclose(out);
    }
    munmap(normal, REGION_SIZE);
    munmap(thp, REGION_SIZE);
    return 0;
}
