#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MM_INTENT_REGISTER_PATH "/sys/kernel/debug/mm_intent/register"

static void usage(const char *prog)
{
	fprintf(stderr,
		"Usage: %s <pid> <start_hex> <length_hex> <flags_hex> <deadline_ns> <priority>\n",
		prog);
}

int main(int argc, char **argv)
{
	char line[256];
	int fd;
	int len;
	ssize_t written;

	if (argc != 7) {
		usage(argv[0]);
		return 1;
	}

	len = snprintf(line, sizeof(line), "%s %s %s %s %s %s\n",
		       argv[1], argv[2], argv[3], argv[4], argv[5], argv[6]);
	if (len < 0 || len >= (int)sizeof(line)) {
		fprintf(stderr, "input too long\n");
		return 1;
	}

	fd = open(MM_INTENT_REGISTER_PATH, O_WRONLY);
	if (fd < 0) {
		fprintf(stderr, "failed to open %s: %s\n",
			MM_INTENT_REGISTER_PATH, strerror(errno));
		fprintf(stderr,
			"hint: make sure debugfs is mounted and the patched kernel is running\n");
		return 1;
	}

	written = write(fd, line, (size_t)len);
	if (written < 0) {
		fprintf(stderr, "failed to write registration: %s\n", strerror(errno));
		close(fd);
		return 1;
	}
	if (written != len) {
		fprintf(stderr, "short write to %s\n", MM_INTENT_REGISTER_PATH);
		close(fd);
		return 1;
	}

	close(fd);
	printf("registered memory-intent range for pid %s\n", argv[1]);
	return 0;
}
