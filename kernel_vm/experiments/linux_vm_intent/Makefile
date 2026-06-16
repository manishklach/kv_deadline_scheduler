CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra

all: kv_madvise_experiment
build: kv_madvise_experiment

kv_madvise_experiment: kv_madvise_experiment.c
	$(CC) $(CFLAGS) -o $@ $<

run: kv_madvise_experiment
	./kv_madvise_experiment

clean:
	rm -f kv_madvise_experiment
