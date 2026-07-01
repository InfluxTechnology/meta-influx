#define _GNU_SOURCE
#include <stdio.h>
#include <dlfcn.h>
#include <string.h>

static int hex_value(char ch)
{
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

static int parse_seed(const char *text, char seed[100], int len)
{
    int high;
    int low;
    unsigned char i;

    for (i = 0; i < len; ++i) {
        high = hex_value(text[i * 2]);
        low = hex_value(text[i * 2 + 1]);
        if (high < 0 || low < 0) {
            return 0;
        }
        seed[i] = (unsigned char)((high << len) | low);
    }

    return text[len*2] == '\0';
}

int main(int argc, char **argv) {
    char buff[64] = "./";
    char *libpath = buff + strlen(buff);
    strcpy(libpath, buff);

    const char *dlname = (argc > 1) ? argv[1] : NULL;
    if (dlname == NULL) return 1;
    char *dlseed = (argc > 2) ? argv[2] : NULL;
    if (dlseed == NULL) return 1;
    char seedlen = strlen(dlseed) / 2;

    if (dlname == NULL) 
	return 1;
    
    strcat(libpath, dlname);

    void *handle = dlopen(libpath, RTLD_LAZY);
    if (!handle) 
        return 1;

    typedef void (*seedkey_t)(const char *, int len);
    dlerror(); 

    seedkey_t calc_key_by_seed = (seedkey_t)dlsym(handle, "calc_key_by_seed");
    char *err = dlerror();
    if (err) {
        dlclose(handle);
        return 1;
    }

    char seed[100];
    parse_seed(dlseed, seed, seedlen);
    calc_key_by_seed(seed, seedlen);

    dlclose(handle);
    return 0;
}
