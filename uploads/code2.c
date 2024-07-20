    #include <stdio.h>

    // Toplama işlemi

    int sub(int x, int y) {
        return x - y;
    }
    int add(int a, int b) {
        return a + b;
    }

    int main() {
        int a = 10, b = 5;
        int x = 15, y = 7;

        int result_add = add(a, b);
        int result_sub = sub(x, y);

        printf("Addition Result: %d\\n", result_add);
        printf("Subtraction Result: %d\\n", result_sub);

        return 0;
    }