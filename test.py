import tree_sitter_python as tspython
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
import difflib
import re

PY_LANGUAGE = Language(tsc.language())

# Tree-sitter parser oluştur
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

def is_exact_clone(code1, code2):
    return code1.strip() == code2.strip()

def renamed_clone_similarity(code1, code2):
    def extract_identifiers(code):
        # Tanımlayıcıları (fonksiyon ve değişken isimleri) çıkart
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
        # Anahtar kelimeleri çıkar
        keywords = {'if', 'else', 'for', 'while', 'return', 'int', 'float', 'double', 'char', 'void', 'include'}
        identifiers = [id for id in identifiers if id not in keywords]
        return set(identifiers)

    ids1 = extract_identifiers(code1)
    ids2 = extract_identifiers(code2)

    return len(ids1 & ids2) / len(ids1 | ids2)

def near_miss_clone_similarity(code1, code2, threshold=0.8):
    # Metin ve token benzerliklerini hesapla
    text_sim = text_similarity(code1, code2)
    token_sim = token_similarity(code1, code2)
    token_sim_without_comments = token_similarity(remove_comments_and_whitespace(code1), remove_comments_and_whitespace(code2))
    
    # Eğer herhangi bir benzerlik oranı eşik değerini geçiyorsa, hafif değiştirilmiş klon olarak kabul et
    return text_sim > threshold or token_sim > threshold or token_sim_without_comments > threshold

def parameterized_clone_similarity(code1, code2, threshold=0.8):
    # Parametre değişikliklerini tespit etmek için metin ve token benzerliklerini kullan
    return near_miss_clone_similarity(code1, code2, threshold)

def function_clone_similarity(code1, code2, threshold=0.8):
    # Fonksiyon seviyesindeki klonları tespit etmek için metin ve token benzerliklerini kullan
    return near_miss_clone_similarity(code1, code2, threshold)

def non_contiguous_clone_similarity(code1, code2, threshold=0.8):
    # Bitişik olmayan klonları tespit etmek için metin ve token benzerliklerini kullan
    # Burada, token benzerliklerine odaklanılabilir
    token_sim_without_order = token_similarity(code1, code2, with_order=False)
    token_sim_with_order = token_similarity(code1, code2, with_order=True)
    return token_sim_without_order > threshold or token_sim_with_order > threshold

def structural_clone_similarity(code1, code2, threshold=0.8):
    # Yapısal benzerlikleri tespit etmek için token benzerliğini kullan
    return token_similarity(code1, code2, with_order=True) > threshold

def reordered_clone_similarity(code1, code2, threshold=0.8):
    # Yeniden sıralanmış klonları tespit etmek için sırasız token benzerliğini kullan
    return token_similarity(code1, code2, with_order=False) > threshold

def function_reordered_clone_similarity(code1, code2, threshold=0.8):
    # Yeniden sıralanmış fonksiyon klonlarını tespit etmek için metin ve token benzerliklerini kullan
    return reordered_clone_similarity(code1, code2, threshold)

def gapped_clone_similarity(code1, code2, threshold=0.8):
    # Boşluklu klonları tespit etmek için metin ve token benzerliklerini kullan
    # Kod parçalarının kısmi benzerliklerini değerlendirir
    tokens1 = parse_code(code1)
    tokens2 = parse_code(code2)
    matcher = difflib.SequenceMatcher(None, tokens1, tokens2)
    blocks = matcher.get_matching_blocks()
    
    match_ratio = sum(triple.size for triple in blocks) / min(len(tokens1), len(tokens2))
    return match_ratio > threshold

def intertwined_clone_similarity(code1, code2, threshold=0.8):
    # İç içe geçmiş klonları tespit etmek için metin ve token benzerliklerini kullan
    tokens1 = parse_code(code1)
    tokens2 = parse_code(code2)
    matcher = difflib.SequenceMatcher(None, tokens1, tokens2)
    blocks = matcher.get_matching_blocks()
    
    match_ratio = sum(triple.size for triple in blocks if triple.size > 1) / min(len(tokens1), len(tokens2))
    return match_ratio > threshold

def semantic_clone_similarity(code1, code2, threshold=0.8):
    # Anlamsal benzerlikleri tespit etmek için metin ve token benzerliklerini kullan
    # Bu, metin ve token benzerliklerini birleştirir
    text_sim = text_similarity(code1, code2)
    token_sim = token_similarity(code1, code2)
    return (text_sim + token_sim) / 2 > threshold

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
    printf("Addition: %d\\n", result_add);
    printf("Subtraction Result: %d\\n", result_sub);

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

    printf("Addition Result: %d\\n", result_add);
    printf("Subtraction Result: %d\\n", result_sub);

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

exact_clone_result = is_exact_clone(code1, code2)
renamed_clone_sim = renamed_clone_similarity(code1, code2)
near_miss_clone_result = near_miss_clone_similarity(code1, code2)
parameterized_clone_result = parameterized_clone_similarity(code1, code2)
function_clone_result = function_clone_similarity(code1, code2)
non_contiguous_clone_result = non_contiguous_clone_similarity(code1, code2)
structural_clone_result = structural_clone_similarity(code1, code2)
reordered_clone_result = reordered_clone_similarity(code1, code2)
function_reordered_clone_result = function_reordered_clone_similarity(code1, code2)
gapped_clone_result = gapped_clone_similarity(code1, code2)
intertwined_clone_result = intertwined_clone_similarity(code1, code2)
semantic_clone_result = semantic_clone_similarity(code1, code2)

print(f"\nText Similarity:\n {percentage_4f(text_sim)}")
print(f"Token Similarity (with order):\n {percentage_4f(token_sim_with_order)}")
print(f"Token Similarity (with order ignoring comments and whitespaces):\n {percentage_4f(token_sim_with_order_without_comments)}")
print(f"Token Similarity (without order with comments and whitespaces):\n {percentage_4f(token_sim)}")
print(f"Token Similarity (without order ignoring comments and whitespaces):\n {percentage_4f(token_sim_without_comments)}")
print(f"Renamed Clone Similarity:\n {percentage_4f(renamed_clone_sim)}")

print(f"\nExact Clone:\n {exact_clone_result}")
print(f"Near-miss Clone:\n {near_miss_clone_result}")
print(f"Parameterized Clone:\n {parameterized_clone_result}")
print(f"Function Clone:\n {function_clone_result}")
print(f"Non-contiguous Clone:\n {non_contiguous_clone_result}")
print(f"Structural Clone:\n {structural_clone_result}")
print(f"Reordered Clone:\n {reordered_clone_result}")
print(f"Function Reordered Clone:\n {function_reordered_clone_result}")
print(f"Gapped Clone:\n {gapped_clone_result}")
print(f"Intertwined Clone:\n {intertwined_clone_result}")
print(f"Semantic Clone:\n {semantic_clone_result}")
