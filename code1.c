#include <stdio.h>
#include <string.h>
 
int main() {
    char str1[100], str2[100];
 
    printf("İlk metni girin: ");
    gets(str1);
 
    strcpy(str2, str1);
 
    printf("Kopyalanan metin: %s\n", str2);
 
    return 0;
}