#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <time.h>
#include <dirent.h>

const unsigned char shell_script[] = {};
const size_t shell_script_len = sizeof(shell_script);

int main() {
    DIR *entry = opendir("/tmp/.ProperTree");
    if (entry == NULL) {
        if (mkdir("/tmp/.ProperTree", 0777) != 0) {
            perror("Failed to create /tmp/.ProperTree.");
        }
    }

    char filename[100] = "/tmp/.ProperTree/script-XXXXXX";
    int fd = mkstemp(filename);

    if (fd == -1) {
        perror("mkstemp");
        return 1;
    }

    if (write(fd, shell_script, shell_script_len) != shell_script_len) {
        perror("write");
        close(fd);
        unlink(filename);
        return 1;
    }

    close(fd);

    if (chmod(filename, 0700) == -1) {
        perror("chmod");
        unlink(filename);
        return 1;
    }

    int status = system(filename);

    unlink(filename);
    return status;
}
