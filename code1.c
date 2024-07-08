#include <stdio.h>

// Toplama işlemi
int sub(int a, int b) {
    return a - b;
}
int add(int a, int b) {
    return a + b;
}

int main() {
    int result_sub = sub(5, 3);
    int result_add = add(5, 3);
    // Sonuçları yazdır
    printf("Addition: %d\\n", result_add);
    printf("Subtraction Result: %d\\n", result_sub);

    return 0;
}