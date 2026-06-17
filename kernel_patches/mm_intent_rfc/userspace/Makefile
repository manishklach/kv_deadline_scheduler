CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra

all: mm_intent_register

mm_intent_register: mm_intent_register.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f mm_intent_register
