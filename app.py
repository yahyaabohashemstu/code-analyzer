from flask import Flask, request,render_template
from clone_detector import clone_detectors,languages
import os
import zipfile



app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def percentage_4f(value):
    return "%{:.4f}".format(value * 100)


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
    language_options_html = ''.join(f'<option value="{language}">{language}</option>' for language in languages)

    code1 = None
    code2 = None
    graph_url1 = None
    graph_url2 = None
    description_list = ''
    chart_url = None

    if request.method == 'POST':
        language = request.form.get('language', 'c')
        detector = clone_detectors.get(language)

        if not detector:
            return render_template('main.html', language_options_html=language_options_html)

        code1 = request.form.get('code1')
        code2 = request.form.get('code2')
        file1 = request.files.get('file1')
        file2 = request.files.get('file2')
        zip1 = request.files.get('zip1')
        zip2 = request.files.get('zip2')

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
        token_sim = detector.token_similarity(code1, code2)
        token_sim_without_comments = detector.token_similarity(clean_code1, clean_code2)
        token_sim_with_order = detector.token_similarity(code1, code2, with_order=True)
        token_sim_with_order_without_comments = detector.token_similarity(clean_code1, clean_code2, with_order=True)

        exact_clone_result = detector.is_exact_clone(code1, code2)
        renamed_clone_sim = detector.renamed_clone_similarity(code1, code2)
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
        graph_sim = detector.graph_similarity(code1, code2)
        combined_similarity = detector.combined_similarity(code1, code2)

        # Generate graph images as base64 strings
        graph_url1 = detector.graph_to_image(code1)
        graph_url2 = detector.graph_to_image(code2)

        values_list = [
            ['Text Similarity:', text_sim * 100],
            ['Token Similarity\n(with order):', token_sim_with_order * 100],
            ['Token Similarity\n(with order ignoring\ncomments and whitespaces):', token_sim_with_order_without_comments * 100],
            ['Token Similarity\n(without order with\ncomments and whitespaces):', token_sim * 100],
            ['Token Similarity\n(without order ignoring\ncomments and whitespaces):', token_sim_without_comments * 100],
            ['Graph-Based Similarity:', graph_sim * 100],
            ['Combined Similarity:', combined_similarity * 100]
        ]

        all_values_list = [
            ['Text Similarity', text_sim * 100],
            ['Token Similarity (with order)', token_sim_with_order * 100],
            ['Token Similarity (with order ignoring comments and whitespaces)', token_sim_with_order_without_comments * 100],
            ['Token Similarity (without order with comments and whitespaces)', token_sim * 100],
            ['Token Similarity (without order ignoring comments and whitespaces)', token_sim_without_comments * 100],
            ['Renamed Clone Similarity', renamed_clone_sim * 100],
            ['Graph-Based Similarity', graph_sim * 100],
            ['Combined Similarity', combined_similarity * 100],
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
            ['Semantic Clone', semantic_clone_result],
        ]

        for i in all_values_list:
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
                status_class = 'true' if i[1] else 'false'
                description_list += f'''
                <div class="result-item">
                    <div class="result-label">{i[0]}:</div>
                    <div class="toggle-container {status_class}">
                        <div class="toggle-switch"></div>
                        <div class="toggle-status">{str(i[1])}</div>
                    </div>
                </div>
                '''

    return render_template('main.html',
                           description_list=description_list,
                           language_options_html=language_options_html,
                           code1=code1,
                           code2=code2,
                           graph_url1=graph_url1,
                           graph_url2=graph_url2)




if __name__ == '__main__':
    app.run(debug=True,port=5001)
