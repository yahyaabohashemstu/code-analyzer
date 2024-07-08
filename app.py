from flask import Flask, request, render_template_string
from tree_sitter_languages import get_parser
import difflib
import re

app = Flask(__name__)

def percentage_4f(value):
    return "{:.4f}".format(value * 100)

# Tree-sitter parser oluştur

class CloneDetector:
    def __init__(self, language):
        self.parser = language_parsers[language]

    def parse_code(self,code, with_order=False):
        tree = self.parser.parse(bytes(code, "utf8"))
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

    def remove_comments_and_whitespace(self,code):
        tree = self.parser.parse(bytes(code, "utf8"))
        root_node = tree.root_node

        def extract_text(node):
            if node.type in ('comment', 'whitespace'):
                return ''
            if node.child_count == 0:
                return node.text.decode('utf8')
            return ''.join([extract_text(child) for child in node.children])

        return extract_text(root_node)

    def text_similarity(self,code1, code2):
        seqm = difflib.SequenceMatcher(None, code1, code2)
        return seqm.ratio()

    def token_similarity(self,code1, code2, with_order=False):
        tokens1 = self.parse_code(code1, with_order)
        tokens2 = self.parse_code(code2, with_order)
        seqm = difflib.SequenceMatcher(None, tokens1, tokens2)
        return seqm.ratio()

    def is_exact_clone(self,code1, code2):
        return code1.strip() == code2.strip()

    def renamed_clone_similarity(self,code1, code2):
        def extract_identifiers(code):
            identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
            keywords = {'if', 'else', 'for', 'while', 'return', 'int', 'float', 'double', 'char', 'void', 'include'}
            identifiers = [id for id in identifiers if id not in keywords]
            return set(identifiers)

        ids1 = extract_identifiers(code1)
        ids2 = extract_identifiers(code2)

        return len(ids1 & ids2) / len(ids1 | ids2)

    def near_miss_clone_similarity(self,code1, code2, threshold=0.8):
        text_sim = self.text_similarity(code1, code2)
        token_sim = self.token_similarity(code1, code2)
        token_sim_without_comments = self.token_similarity(self.remove_comments_and_whitespace(code1), self.remove_comments_and_whitespace(code2))
        return text_sim > threshold or token_sim > threshold or token_sim_without_comments > threshold

    def parameterized_clone_similarity(self,code1, code2, threshold=0.8):
        return self.near_miss_clone_similarity(code1, code2, threshold)

    def function_clone_similarity(self,code1, code2, threshold=0.8):
        return self.near_miss_clone_similarity(code1, code2, threshold)

    def non_contiguous_clone_similarity(self,code1, code2, threshold=0.8):
        token_sim_without_order = self.token_similarity(code1, code2, with_order=False)
        token_sim_with_order = self.token_similarity(code1, code2, with_order=True)
        return token_sim_without_order > threshold or token_sim_with_order > threshold

    def structural_clone_similarity(self,code1, code2, threshold=0.8):
        return self.token_similarity(code1, code2, with_order=True) > threshold

    def reordered_clone_similarity(self,code1, code2, threshold=0.8):
        return self.token_similarity(code1, code2, with_order=False) > threshold

    def function_reordered_clone_similarity(self,code1, code2, threshold=0.8):
        return self.reordered_clone_similarity(code1, code2, threshold)

    def gapped_clone_similarity(self,code1, code2, threshold=0.8):
        tokens1 = self.parse_code(code1)
        tokens2 = self.parse_code(code2)
        matcher = difflib.SequenceMatcher(None, tokens1, tokens2)
        blocks = matcher.get_matching_blocks()
        match_ratio = sum(triple.size for triple in blocks) / min(len(tokens1), len(tokens2))
        return match_ratio > threshold

    def intertwined_clone_similarity(self,code1, code2, threshold=0.8):
        tokens1 = self.parse_code(code1)
        tokens2 = self.parse_code(code2)
        matcher = difflib.SequenceMatcher(None, tokens1, tokens2)
        blocks = matcher.get_matching_blocks()
        match_ratio = sum(triple.size for triple in blocks if triple.size > 1) / min(len(tokens1), len(tokens2))
        return match_ratio > threshold

    def semantic_clone_similarity(self,code1, code2, threshold=0.8):
        text_sim = self.text_similarity(code1, code2)
        token_sim =self.token_similarity(code1, code2)
        return (text_sim + token_sim) / 2 > threshold
languages = ['c', 'python', 'java', 'javascript']
language_parsers = {}
for language in languages:
    print(f'Loading parser for {language}...')
    language_parsers[language] = get_parser(language)
clone_detectors = {}    
for language in languages:
    clone_detectors[language] = CloneDetector(language)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        code1 = request.form['code1']
        code2 = request.form['code2']
        language = request.form.get('language', 'c')
        detector = clone_detectors[language]

        clean_code1 = detector.remove_comments_and_whitespace(code1)
        clean_code2 = detector.remove_comments_and_whitespace(code2)

        text_sim = detector.text_similarity(code1, code2)
        text_sim = percentage_4f(text_sim)
        token_sim = detector.token_similarity(code1, code2)
        token_sim = percentage_4f(token_sim)
        token_sim_without_comments = detector.token_similarity(clean_code1, clean_code2)
        token_sim_without_comments = percentage_4f(token_sim_without_comments)
        token_sim_with_order = detector.token_similarity(code1, code2, with_order=True)
        token_sim_with_order = percentage_4f(token_sim_with_order)
        token_sim_with_order_without_comments = detector.token_similarity(clean_code1, clean_code2, with_order=True)
        token_sim_with_order_without_comments = percentage_4f(token_sim_with_order_without_comments)

        exact_clone_result = detector.is_exact_clone(code1, code2)
        renamed_clone_sim = detector.renamed_clone_similarity(code1, code2)
        renamed_clone_sim = percentage_4f(renamed_clone_sim)
        near_miss_clone_result = detector.near_miss_clone_similarity(code1, code2)
        parameterized_clone_result = detector.parameterized_clone_similarity(code1, code2)
        function_clone_result = detector.function_clone_similarity(code1, code2)
        non_contiguous_clone_result = detector.non_contiguous_clone_similarity(code1, code2)
        structural_clone_result = detector.structural_clone_similarity(code1, code2)
        reordered_clone_result = detector.reordered_clone_similarity(code1, code2)
        function_reordered_clone_result = detector.function_reordered_clone_similarity(code1, code2)
        gapped_clone_result = detector.gapped_clone_similarity(code1, code2)
        intertwined_clone_result = detector.intertwined_clone_similarity(code1, code2)
        semantic_clone_result = detector.semantic_clone_similarity(code1, code2)
        language_options_html = ''
        for language in languages:
            language_options_html += f'<option value="{language}">{language}</option>'
        print(language_options_html)
                

        return render_template_string('''
  <!DOCTYPE html>
<html>

<head>
    <title>Title</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="css/uikit.min.css" />
    <script src="js/uikit.min.js"></script>
    <script src="js/uikit-icons.min.js"></script>
</head>

<body>
    <form method="POST">
        <textarea name="code1" rows="10" cols="50">{{code1}}</textarea>
        <textarea name="code2" rows="10" cols="50">{{code2}}</textarea>
        <select name="language">
            {{language_options_html}}
        </select>
        <input type="submit" value="Compare">
    </form>
    <p>Text Similarity: {{text_sim}}</p>
    <p>Token Similarity (with order): {{token_sim_with_order}}</p>
    <p>Token Similarity (with order ignoring comments and whitespaces): {{token_sim_with_order_without_comments}}</p>
    <p>Token Similarity (without order with comments and whitespaces): {{token_sim}}</p>
    <p>Token Similarity (without order ignoring comments and whitespaces): {{token_sim_without_comments}}</p>
    <p>Renamed Clone Similarity: {{renamed_clone_sim}}</p>
    <p>Exact Clone: {{exact_clone_result}}</p>
    <p>Near-miss Clone: {{near_miss_clone_result}}</p>
    <p>Parameterized Clone: {{parameterized_clone_result}}</p>
    <p>Function Clone: {{function_clone_result}}</p>
    <p>Non-contiguous Clone: {{non_contiguous_clone_result}}</p>
    <p>Structural Clone: {{structural_clone_result}}</p>
    <p>Reordered Clone: {{reordered_clone_result}}</p>
    <p>Function Reordered Clone: {{function_reordered_clone_result}}</p>
    <p>Gapped Clone: {{gapped_clone_result}}</p>
    <p>Intertwined Clone: {{intertwined_clone_result}}</p>
    <p>Semantic Clone: {{semantic_clone_result}}</p>
</body>

</html>
           
        ''', **locals())

    return render_template_string('''
 <!DOCTYPE html>
<html>

<head>
    <title>Title</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" href="css/uikit.min.css" />
    <script src="js/uikit.min.js"></script>
    <script src="js/uikit-icons.min.js"></script>
</head>

<body>
    <form method="POST">
        <textarea name="code1" rows="10" cols="50"></textarea>
        <textarea name="code2" rows="10" cols="50"></textarea>
         <select name="language">
            {{language_options_html}}
        </select>
        <input type="submit" value="Compare">
    </form>
</body>

</html>
    ''')

if __name__ == '__main__':
    app.run(debug=True)