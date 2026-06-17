CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -std=c11

all:
	$(CC) $(CFLAGS) test_abi.c memory_intent_ring.c -o test_abi && ./test_abi

clean:
	rm -f test_abi
