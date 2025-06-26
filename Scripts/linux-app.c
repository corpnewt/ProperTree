#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <time.h>
#include <dirent.h>
#include <sys/wait.h>

const unsigned char shell_script[] = {}; // Placeholder, as raw bytes will be written here by buildapp-linux.py
const size_t shell_script_len = sizeof(shell_script);

int main(int argc, char *argv[]) {
    DIR *entry = opendir("/tmp/.ProperTree");
    if (entry == NULL) {
        if (mkdir("/tmp/.ProperTree", 0777) != 0) { // Make /tmp/.ProperTree if it doesn't exist
            perror("mkdir");
        }
    }

    char filename[100] = "/tmp/.ProperTree/script-XXXXXX"; // Generate the script's name to be extracted and ran
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

    char **exec_args = malloc(sizeof(char *) * (argc + 1));
    if (!exec_args) {
        perror("malloc");
        unlink(filename);
        return 1;
    }

    exec_args[0] = filename;
    for (int i = 1; i < argc; i++) {
        exec_args[i] = argv[i];
    }

    exec_args[argc] = NULL;
    pid_t pid = fork();

    if (pid == -1) {
        perror("fork");
        free(exec_args);
        unlink(filename);
        return 1;
    } else if (pid == 0) {
        execv(filename, exec_args);
        perror("execv");
        _exit(127);
    } else {
        int status;
        waitpid(pid, &status, 0);
        remove(filename);
        free(exec_args);
        return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
    }
}
