#include <stdio.h>

void calc_key_by_seed(const char *seed, int len)
{
    // input is char array in hex format ('11223344' for example )

    // type here own seed/key algorithm
    unsigned char key[len];
    for (int i = 0; i < len; i++) key[i] = seed[i] << 1;

    // output is in stdout with hex format (4 bytes in example)  
    printf("%02X%02X%02X%02X\n", key[0], key[1], key[2], key[3]);
}
