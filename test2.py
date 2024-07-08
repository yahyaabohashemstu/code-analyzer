import tree_sitter_c as tsc
from tree_sitter import Language, Parser
import difflib

PY_LANGUAGE = Language(tsc.language())

parser = Parser()
parser.set_language(PY_LANGUAGE)

def parse_code(code, with_order=False):
    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node
    tokens = []
    def traverse(node):
        if node.child_count == 0:
            tokens.append(node.type)
        for child in node.children:
            traverse(child)
    traverse(root_node)
    if with_order:
        return tokens
    tokens.sort()
    return tokens

def remove_comments_and_whitespace(code):
    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node

    def extract_text(node):
        if node.type in ('comment', 'whitespace'):
            return ''
        if node.child_count == 0:
            return node.text.decode('utf8')
        return ''.join([extract_text(child) for child in node.children])

    return extract_text(root_node)

def text_similarity(code1, code2):
    seqm = difflib.SequenceMatcher(None, code1, code2)
    return seqm.ratio()

def token_similarity(code1, code2, with_order=False):
    tokens1 = parse_code(code1, with_order)
    tokens2 = parse_code(code2, with_order)
    seqm = difflib.SequenceMatcher(None, tokens1, tokens2)
    return seqm.ratio()

# İki kod parçası
code1 = """
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
    printf("Addition: %d\n", result_add);
    printf("Subtraction Result: %d\n", result_sub);

    return 0;
}
"""

code2 = """
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

    printf("Addition Result: %d\n", result_add);
    printf("Subtraction Result: %d\n", result_sub);

    return 0;
}
"""

def percentage_4f(value):
    return "%{:.4f}".format(value * 100)

clean_code1 = remove_comments_and_whitespace(code1)
clean_code2 = remove_comments_and_whitespace(code2)

text_sim = text_similarity(code1, code2)
token_sim = token_similarity(code1, code2)
token_sim_without_comments = token_similarity(clean_code1, clean_code2)
token_sim_with_order = token_similarity(code1, code2, with_order=True)
token_sim_with_order_without_comments = token_similarity(clean_code1, clean_code2, with_order=True)

print(f"\nText Similarity:\n {percentage_4f(text_sim)}")
print(f"Token Similarity (with order):\n {percentage_4f(token_sim_with_order)}")
print(f"Token Similarity (with order ignoring comments and whitespaces):\n {percentage_4f(token_sim_with_order_without_comments)}")
print(f"Token Similarity (without order with comments and whitespaces):\n {percentage_4f(token_sim)}")
print(f"Token Similarity (without order ignoring comments and whitespaces):\n {percentage_4f(token_sim_without_comments)}\n")