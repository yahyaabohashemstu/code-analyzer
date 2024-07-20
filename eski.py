from flask import Flask, request, render_template_string
from tree_sitter_languages import get_parser
from fuzzywuzzy import fuzz
import re
import os
import zipfile

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def percentage_4f(value):
    return "%{:.4f}".format(value * 100)

class CloneDetector:
    def __init__(self, language):
        self.parser = language_parsers[language]

    def parse_code(self, code, with_order=False):
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

    def remove_comments_and_whitespace(self, code):
        tree = self.parser.parse(bytes(code, "utf8"))
        root_node = tree.root_node

        def extract_text(node):
            if node.type in ('comment', 'whitespace'):
                return ''
            if node.child_count == 0:
                return node.text.decode('utf8')
            return ''.join([extract_text(child) for child in node.children])

        return extract_text(root_node)

    def text_similarity(self, code1, code2):
        return fuzz.ratio(code1, code2) / 100

    def token_similarity(self, code1, code2, with_order=False):
        tokens1 = self.parse_code(code1, with_order)
        tokens2 = self.parse_code(code2, with_order)
        return fuzz.ratio(' '.join(tokens1), ' '.join(tokens2)) / 100

    def is_exact_clone(self, code1, code2):
        return code1.strip() == code2.strip()

    def renamed_clone_similarity(self, code1, code2):
        def extract_identifiers(code):
            identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
            keywords = {'if', 'else', 'for', 'while', 'return', 'int', 'float', 'double', 'char', 'void', 'include'}
            identifiers = [id for id in identifiers if id not in keywords]
            return set(identifiers)

        ids1 = extract_identifiers(code1)
        ids2 = extract_identifiers(code2)

        return len(ids1 & ids2) / len(ids1 | ids2)

    def near_miss_clone_similarity(self, code1, code2, threshold=0.8):
        text_sim = self.text_similarity(code1, code2)
        token_sim = self.token_similarity(code1, code2)
        token_sim_without_comments = self.token_similarity(self.remove_comments_and_whitespace(code1), self.remove_comments_and_whitespace(code2))
        return text_sim > threshold or token_sim > threshold or token_sim_without_comments > threshold

    def parameterized_clone_similarity(self, code1, code2, threshold=0.8):
        return self.near_miss_clone_similarity(code1, code2, threshold)

    def function_clone_similarity(self, code1, code2, threshold=0.8):
        return self.near_miss_clone_similarity(code1, code2, threshold)

    def non_contiguous_clone_similarity(self, code1, code2, threshold=0.8):
        token_sim_without_order = self.token_similarity(code1, code2, with_order=False)
        token_sim_with_order = self.token_similarity(code1, code2, with_order=True)
        return token_sim_without_order > threshold or token_sim_with_order > threshold

    def structural_clone_similarity(self, code1, code2, threshold=0.8):
        return self.token_similarity(code1, code2, with_order=True) > threshold

    def reordered_clone_similarity(self, code1, code2, threshold=0.8):
        return self.token_similarity(code1, code2, with_order=False) > threshold

    def function_reordered_clone_similarity(self, code1, code2, threshold=0.8):
        return self.reordered_clone_similarity(code1, code2, threshold)

    def gapped_clone_similarity(self, code1, code2, threshold=0.8):
        tokens1 = self.parse_code(code1)
        tokens2 = self.parse_code(code2)
        match_ratio = fuzz.ratio(' '.join(tokens1), ' '.join(tokens2)) / 100
        return match_ratio > threshold

    def intertwined_clone_similarity(self, code1, code2, threshold=0.8):
        tokens1 = self.parse_code(code1)
        tokens2 = self.parse_code(code2)
        match_ratio = fuzz.partial_ratio(' '.join(tokens1), ' '.join(tokens2)) / 100
        return match_ratio > threshold

    def semantic_clone_similarity(self, code1, code2, threshold=0.8):
        text_sim = self.text_similarity(code1, code2)
        token_sim = self.token_similarity(code1, code2)
        return (text_sim + token_sim) / 2 > threshold

languages = [
    'c', 'python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'go',
    'swift', 'typescript', 'php', 'kotlin', 'r', 'dart', 'rust',
    'scala', 'elixir', 'haskell', 'perl', 'objective-c'
]
language_parsers = {}
clone_detectors = {}
for language in languages:
    try:
        print(f'Loading parser for {language}...')
        language_parsers[language] = get_parser(language)
        clone_detectors[language] = CloneDetector(language)
    except Exception as e:
        print(f'Error loading parser for {language}: {e}')

def extract_zip(file_path):
    extracted_files = []
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(app.config['UPLOAD_FOLDER'])
        for root, _, files in os.walk(app.config['UPLOAD_FOLDER']):
            for file in files:
                if file.endswith(('.c', '.py', '.java', '.js', '.cpp', '.cs', '.rb', '.go', '.swift', '.ts', '.php', '.kt', '.r', '.dart', '.rs', '.scala', '.ex', '.hs', '.pl', '.m')):
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        extracted_files.append(f.read())
    return extracted_files

@app.route('/', methods=['GET', 'POST'])
def index():
    language_options_html = ''
    for language in languages:
        language_options_html += f'<option value="{language}">{language}</option>'

    code1 = request.form.get('code1')
    code2 = request.form.get('code2')
    file1 = request.files.get('file1')
    file2 = request.files.get('file2')
    zip1 = request.files.get('zip1')
    zip2 = request.files.get('zip2')
    description_list = ''

    if request.method == 'POST':
        language = request.form.get('language', 'c')
        detector = clone_detectors.get(language)

        if not detector:
            return render_template_string(template, **locals())

        if zip1 and zipfile.is_zipfile(zip1):
            code1_files = extract_zip(zip1)
            code1 = "\n".join(code1_files)
        elif file1:
            code1 = file1.read().decode('utf-8')

        if zip2 and zipfile.is_zipfile(zip2):
            code2_files = extract_zip(zip2)
            code2 = "\n".join(code2_files)
        elif file2:
            code2 = file2.read().decode('utf-8')

        clean_code1 = detector.remove_comments_and_whitespace(code1)
        clean_code2 = detector.remove_comments_and_whitespace(code2)

        text_sim = detector.text_similarity(code1, code2)
        text_sim = float(text_sim * 100)
        token_sim = detector.token_similarity(code1, code2)
        token_sim = float(token_sim * 100)
        token_sim_without_comments = detector.token_similarity(clean_code1, clean_code2)
        token_sim_without_comments = float(token_sim_without_comments * 100)
        token_sim_with_order = detector.token_similarity(code1, code2, with_order=True)
        token_sim_with_order = float(token_sim_with_order * 100)
        token_sim_with_order_without_comments = detector.token_similarity(clean_code1, clean_code2, with_order=True)
        token_sim_with_order_without_comments = float(token_sim_with_order_without_comments * 100)

        exact_clone_result = detector.is_exact_clone(code1, code2)
        renamed_clone_sim = detector.renamed_clone_similarity(code1, code2)
        renamed_clone_sim = float(renamed_clone_sim * 100)
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

        values_list = [
            ['Text Similarity', text_sim],
            ['Token Similarity (with order)', token_sim_with_order],
            ['Token Similarity (with order ignoring comments and whitespaces)', token_sim_with_order_without_comments],
            ['Token Similarity (without order with comments and whitespaces)', token_sim],
            ['Token Similarity (without order ignoring comments and whitespaces)', token_sim_without_comments],
            ['Renamed Clone Similarity', renamed_clone_sim],
            ['Exact Clone', exact_clone_result],
            ['Near-miss Clone', near_miss_clone_result],
            ['Parameterized Clone', parameterized_clone_result],
            ['Function Clone', function_clone_result],
            ['Non-contiguous Clone', non_contiguous_clone_result],
            ['Structural Clone', structural_clone_result],
            ['Reordered Clone', reordered_clone_result],
            ['Function Reordered Clone', function_reordered_clone_result],
            ['Gapped Clone', gapped_clone_result],
            ['Intertwined Clone', intertwined_clone_result],
            ['Semantic Clone', semantic_clone_result]
        ]

        for i in values_list:
            if isinstance(i[1], float):
                color_class = ""
                if i[1] < 40:
                    color_class = "color1"
                elif 40 <= i[1] < 50:
                    color_class = "color2"
                elif 50 <= i[1] < 60:
                    color_class = "color3"
                elif 60 <= i[1] < 70:
                    color_class = "color4"
                elif 70 <= i[1] < 80:
                    color_class = "color5"
                elif 80 <= i[1] < 90:
                    color_class = "color6"
                else:
                    color_class = "color7"

                description_list += f'''
                <div class="result-item">
                    <div class="result-label">{i[0]}:</div>
                    <div class="circle-container {color_class}" data-percentage="{i[1]:.2f}">
                        <svg>
                            <circle class="circle-bg" cx="50" cy="50" r="45"></circle>
                            <circle class="circle hover-effect" cx="50" cy="50" r="45"></circle>
                        </svg>
                        <div class="circle-text">{i[1]:.2f}%</div>
                    </div>
                </div>
                '''
            else:
                status_class = 'true' if i[1] == True else 'false'
                description_list += f'''
                <div class="result-item">
                    <div class="result-label">{i[0]}:</div>
                    <div class="toggle-container {status_class}">
                        <div class="toggle-switch"></div>
                        <div class="toggle-status">{str(i[1])}</div>
                    </div>
                </div>
                '''

    return render_template_string(template, **locals())

template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clone Detector</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
   <style>
    :root {
        --primary-color: #6a0dad;
        --secondary-color: #f0f0f0;
        --font-color: #333;
        --input-bg-color: #fff;
        --placeholder-color: #888;
        --label-color: black;
        --circle-bg-color: white;
        --color1: #d2b4de;
        --color2: #c39bd3;
        --color3: #9b59b6;
        --color4: #8e44ad;
        --color5: #7d3c98;
        --color6: var(--primary-color);
        --color7: #5e35b1;
        --color8: #4b0082;
    }

    body {
        background-color: var(--secondary-color);
        font-family: 'Arial', sans-serif;
        margin: 0;
        padding: 0;
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100%;
    }

    .container {
        background-color: var(--secondary-color);
        border-radius: 16px;
        padding-right: 150px;
        padding-left: 150px;
        width: 80%;
        margin-bottom: 50px;
    }

    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
    }

    .header-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
    }

    .header h1 {
        margin: 0;
        padding: 0;
        color: var(--primary-color);
    }

        .logo-container {
            position: relative;
            width: 530px; /* Logo container genişliği */
            height: 100px; /* Logo container yüksekliği */
            overflow: hidden;
            margin-top: 20px;
            display: flex;
            justify-content: flex-end; /* Logoyu sağa hizala */
            align-items: center; /* Dikey ortalama */
        }

        .logo-container .logo {
            width: 50px; /* Logo genişliği */
            height: 80px; /* Logo yüksekliği */
            transition: transform 0.5s ease; /* Transform geçişi ekleyin */
            margin-right: 10px; /* Logo sağdan boşluk */
        }

        .logo-container:hover .logo {
            transform: scale(1.2); /* Hover durumunda logo ölçeklendir */
        /*    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.80); /* Hover durumunda gölgelendirme */*/
        }

        .logo-container .logo-name {
            position: absolute;
            top: 50%;
            right: 45px; /* Sağdan başlangıç konumu */
            width: 400px; /* Logo adı genişliği */
            height: 30px; /* Logo adı yüksekliği */
            opacity: 0;
            transform: translateY(-50%) translateX(20px);
            transition: transform 0.5s ease, opacity 0.5s ease;
        }

        .logo-container:hover .logo-name {
            transform: translateY(-50%) translateX(-40px); /* Hover durumunda sağdan konum ve kaydırma */
            opacity: 1;
        }


    .form-group {
        margin-top: 70px;
    }

    .form-group label {
        display: block;
        margin-bottom: 5px;
        color: var(--label-color);
    }

    .form-group textarea, .form-group select, .form-group input {
        width: 100%;
        padding: 10px;
        border: none;
        border-radius: 8px;
        background-color: var(--input-bg-color);
        resize: vertical;
    }

    .form-group textarea {
        height: 150px;
    }

    .form-group select {
        height: 45px;
        width: 200px;
        font-size: 17px;
    }

    .form-group .button {
        display: block;
        width: 200px;
        padding: 10px;
        border: 1px solid var(--primary-color);
        border-radius: 8px;
        background-color: var(--primary-color);
        color: var(--input-bg-color);
        font-size: 16px;
        cursor: pointer;
        transition: background-color 0.3s;
        margin-top: 30px;
        margin-bottom: 70px;
    }

    .form-group .button:hover {
        border: 1px solid var(--primary-color);
        background-color: var(--secondary-color);
        color: var(--primary-color);
    }

    .upload-container {
        display: flex;
        gap: 20px;
        margin-bottom: 20px;
    }

    .upload-button {
        margin-top: 20px;
        display: flex;
        align-items: center;
        padding: 5px;
        box-shadow: 0 1px 1px rgba(0, 0, 0, 0.1);
        width: 250px;
        background-color: var(--input-bg-color);
        border-radius: 8px;
        transition: transform 0.3s;
        cursor: pointer;
        position: relative;
        overflow: hidden;
    }

    .upload-button::before {
        content: "";
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: var(--primary-color);
        transition: transform 0.4s cubic-bezier(0.3, 1, 0.8, 1);
        z-index: 0;
    }

    .upload-button:hover::before {
        transform: translateX(100%);
    }

    .upload-button .icon, .upload-button .text {
        position: relative;
        z-index: 10;
        transition: color 0.4s;
    }

    .upload-button .text:hover {
        color: white;
    }

    .upload-button:hover {
        transform: translateY(-3px);
    }

    .upload-button:hover .text {
        color: var(--secondary-color);
    }

    .upload-button:active {
        transform: translateY(2px);
    }

    .upload-button .icon {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 35px;
        height: 35px;
        background-color: var(--primary-color);
        border-radius: 8px;
        margin-right: 20px;
        transition: background-color 0.3s ease;
    }

    .upload-button .icon span {
        color: var(--input-bg-color);
        font-size: 30px;
    }

    .upload-button .text {
        font-size: 18px;
        color: var(--font-color);
        text-align: center;
    }

    .upload-button:hover .icon {
        background-color: var(--secondary-color);
    }

    .upload-button:hover .icon span {
        color: var(--primary-color);
    }

    .upload-button.completed-upload {
        background-color: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--secondary-color);
    }

    .upload-button.completed-upload .icon {
        background-color: var(--primary-color);
        border-color: var(--primary-color);
    }

    .upload-button.completed-upload .icon span {
        color: var(--secondary-color);
    }

    .upload-button.completed-upload .text {
        color: white;
    }

    .remove-file {
        position: absolute;
        top: 5px;
        right: 5px;
        background-color: var(--primary-color);
        color: white;
        border: none;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-size: 16px;
        line-height: 1;
        z-index: 10;
    }

    .remove-file:hover {
        background-color: #5e35b1;
    }

    .results {
        margin-top: 20px;
    }

    .results dl {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
    }

    .results dt {
        font-weight: bold;
        color: #555;
    }

    .results dd {
        margin: 0;
        color: #777;
    }

    .result-item {
        display: flex;
        align-items: center;
        margin-bottom: 20px;
    }

    .result-label {
        width: 250px;
        font-weight: bold;
        color: #555;
    }

    .circle-container {
        position: relative;
        width: 100px;
        height: 100px;
    }

    .circle-container svg {
        width: 100%;
        height: 100%;
    }

    .circle-container .circle-bg {
        fill: none;
        stroke: var(--circle-bg-color);
        stroke-width: 8;
    }

    .circle-container .circle {
        fill: none;
        stroke-width: 8;
        stroke-linecap: round;
        transform: rotate(-90deg);
        transform-origin: 50% 50%;
        stroke-dasharray: 282.6;
        stroke-dashoffset: calc(282.6 - (var(--percentage, 0) / 100) * 282.6);
        transition: stroke-dashoffset 0.6s ease;
    }

    .circle-container:hover .circle {
        stroke-dashoffset: 282.6;
        transition: none;
    }

    .circle-container:hover .circle.hover-effect {
        stroke-dashoffset: calc(282.6 - (var(--percentage, 0) / 100) * 282.6);
        transition: stroke-dashoffset 0.6s ease;
    }

    .circle-container.color1 .circle {
        stroke: var(--color1);
    }

    .circle-container.color2 .circle {
        stroke: var(--color2);
    }

    .circle-container.color3 .circle {
        stroke: var(--color3);
    }

    .circle-container.color4 .circle {
        stroke: var(--color4);
    }

    .circle-container.color5 .circle {
        stroke: var(--color5);
    }

    .circle-container.color6 .circle {
        stroke: var(--color6);
    }

    .circle-container.color7 .circle {
        stroke: var(--color7);
    }

    .circle-container .circle-text {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-size: 18px;
        font-weight: bold;
        transition: all 0.3s ease;
    }

    .toggle-container {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .toggle-switch {
        width: 40px;
        height: 20px;
        border-radius: 10px;
        background-color: var(--placeholder-color);
        position: relative;
        cursor: pointer;
    }

    .toggle-switch::after {
        content: '';
        position: absolute;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background-color: var(--input-bg-color);
        top: 1px;
        left: 1px;
        transition: 0.3s;
    }

    .toggle-container.true .toggle-switch {
        background-color: var(--primary-color);
    }

    .toggle-container.true .toggle-switch::after {
        left: 21px;
    }

    .toggle-status {
        font-weight: bold;
        color: var(--label-color);
    }

    .toggle-container.true .toggle-status {
        color: var(--primary-color);
    }
</style>

</head>
<body>
    <div class="container">
<div class="header">
    <div class="header-content">
        <h1>Clone Detector</h1>
        <div class="logo-container">
            <img src="/static/logo.png" alt="Logo" class="logo">
            <img src="/static/nameOfLogo.png" alt="Logo Name" class="logo-name">
        </div>
    </div>
</div>

        <form method="POST" enctype="multipart/form-data">
            <div class="form-group">
                <label for="code1">Code 1:</label>
                <textarea id="code1" name="code1" placeholder="Paste your first code here...">{{code1|safe}}</textarea>
            </div>
            <div class="upload-container">
                <label for="file1" class="upload-button">
                    <div class="icon">
                        <span>+</span>
                    </div>
                    <div class="text">Upload code File 1</div>
                </label>
                <input type="file" id="file1" name="file1" style="display: none;">
                <label for="zip1" class="upload-button">
                    <div class="icon">
                        <span>+</span>
                    </div>
                    <div class="text">Upload Project 1 (ZIP)</div>
                </label>
                <input type="file" id="zip1" name="zip1" style="display: none;">
            </div>
            <div class="form-group">
                <label for="code2">Code 2:</label>
                <textarea id="code2" name="code2" placeholder="Paste your second code here...">{{code2|safe}}</textarea>
            </div>
            <div class="upload-container">
                <label for="file2" class="upload-button">
                    <div class="icon">
                        <span>+</span>
                    </div>
                    <div class="text">Upload code File 2</div>
                </label>
                <input type="file" id="file2" name="file2" style="display: none;">
                <label for="zip2" class="upload-button">
                    <div class="icon">
                        <span>+</span>
                    </div>
                    <div class="text">Upload Project 2 (ZIP)</div>
                </label>
                <input type="file" id="zip2" name="zip2" style="display: none;">
            </div>
            <div class="form-group">
                <label for="language">Language:</label>
                <select id="language" name="language">
                    {{language_options_html|safe}}
                </select>
            </div>
            <div class="form-group">
                <div class="button-container">
                    <button type="submit" class="button">Compare</button>
                </div>
            </div>
        </form>
        {% if request.method == 'POST' %}
        <div class="results">
            <hr>
            <dl>
                {{description_list|safe}}
            </dl>
        </div>
        {% endif %}
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('.upload-button').forEach(button => {
                const input = button.nextElementSibling;

                button.addEventListener('click', (event) => {
                    if (!button.classList.contains('completed-upload')) {
                        input.click();
                    }
                });

                input.addEventListener('change', (event) => {
                    const fileName = input.files.length > 0 ? input.files[0].name : '';
                    if (fileName) {
                        button.querySelector('.icon').innerHTML = '<span>&#10004;</span>'; // DoÄŸru iÅŸareti
                        button.querySelector('.text').innerText = fileName;
                        button.classList.add('completed-upload');
                        if (!button.querySelector('.remove-file')) {
                            const removeButton = document.createElement('button');
                            removeButton.classList.add('remove-file');
                            removeButton.innerHTML = '<i class="fa-regular fa-trash-can"></i>'; // Font Awesome Ã§Ã¶p kutusu ikonu
                            button.appendChild(removeButton);
                            removeButton.addEventListener('click', (e) => {
                                e.stopPropagation();  // Dosya seÃ§im penceresinin aÃ§Ä±lmasÄ±nÄ± engelle
                                e.preventDefault();  // VarsayÄ±lan davranÄ±ÅŸÄ± engelle
                                input.value = '';  // Dosya seÃ§im inputunu temizle
                                button.querySelector('.icon').innerHTML = '<span>+</span>';
                                button.querySelector('.text').innerText = 'Upload code File 1';
                                button.classList.remove('completed-upload');
                                button.removeChild(removeButton);
                            });
                        }
                    } else {
                        button.querySelector('.icon').innerHTML = '<span>+</span>';
                        button.querySelector('.text').innerText = 'Upload code File 1';
                        button.classList.remove('completed-upload');
                        const removeButton = button.querySelector('.remove-file');
                        if (removeButton) {
                            button.removeChild(removeButton);
                        }
                    }
                });

            });

            // JavaScript to set the strokeDashoffset directly based on data-percentage
            document.querySelectorAll('.circle-container').forEach(container => {
                const percentage = container.getAttribute('data-percentage');
                const circle = container.querySelector('.circle');
                circle.style.strokeDashoffset = 282.6 - (percentage / 100) * 282.6;

                container.addEventListener('mouseover', () => {
                    circle.classList.remove('hover-effect');
                    circle.style.strokeDashoffset = 282.6;
                    setTimeout(() => {
                        circle.classList.add('hover-effect');
                        circle.style.strokeDashoffset = 282.6 - (percentage / 100) * 282.6;
                    }, 10); // ØµØºÙŠØ± ØªØ£Ø®ÙŠØ± Ù„Ø¶Ù…Ø§Ù† Ø§Ù„ØªØ£Ø«ÙŠØ± ÙŠØªÙ… ØªØ´ØºÙŠÙ„Ù‡

                    // Increment number from 0 to percentage
                    const textElement = container.querySelector('.circle-text');
                    let currentNumber = 0;
                    const targetNumber = parseFloat(percentage);
                    const increment = targetNumber / 60; // 1 second animation at 60 FPS
                    const interval = setInterval(() => {
                        currentNumber += increment;
                        if (currentNumber >= targetNumber) {
                            currentNumber = targetNumber;
                            clearInterval(interval);
                        }
                        textElement.innerText = currentNumber.toFixed(2) + '%';
                    }, 16); // Approximately 60 FPS
                });

                container.addEventListener('mouseout', () => {
                    circle.classList.remove('hover-effect');
                    circle.style.strokeDashoffset = 282.6 - (percentage / 100) * 282.6;

                    // Reset the number back to the target value immediately
                    const textElement = container.querySelector('.circle-text');
                    textElement.innerText = parseFloat(percentage).toFixed(2) + '%';
                });
            });
        });
    </script>
</body>
</html>

'''

if __name__ == '__main__':
    app.run(debug=True)