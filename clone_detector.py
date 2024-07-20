

from tree_sitter_languages import get_parser
from fuzzywuzzy import fuzz
import re
import networkx as nx

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

    def code_to_graph(self, code):
        tree = self.parser.parse(bytes(code, "utf8"))
        root_node = tree.root_node
        G = nx.DiGraph()

        def add_nodes(node, parent=None):
            G.add_node(node.id, type=node.type, start=node.start_point, end=node.end_point)
            if parent:
                G.add_edge(parent.id, node.id)
            for child in node.children:
                add_nodes(child, node)

        add_nodes(root_node)
        return G

    def calculate_graph_metrics(self, G):
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()
        avg_degree = sum(dict(G.degree()).values()) / num_nodes
        return num_nodes, num_edges, avg_degree

    def graph_similarity(self, code1, code2):
        graph1 = self.code_to_graph(code1)
        graph2 = self.code_to_graph(code2)

        metrics1 = self.calculate_graph_metrics(graph1)
        metrics2 = self.calculate_graph_metrics(graph2)

        node_sim = 1 - abs(metrics1[0] - metrics2[0]) / max(metrics1[0], metrics2[0])
        edge_sim = 1 - abs(metrics1[1] - metrics2[1]) / max(metrics1[1], metrics2[1])
        degree_sim = 1 - abs(metrics1[2] - metrics2[2]) / max(metrics1[2], metrics2[2])

        return (node_sim + edge_sim + degree_sim) / 3

    def combined_similarity(self, code1, code2):
        text_sim = self.text_similarity(code1, code2)
        token_sim = self.token_similarity(code1, code2)
        graph_sim = self.graph_similarity(code1, code2)
        return (text_sim + token_sim + graph_sim) / 3

languages = [
    'c', 'python', 'java', 'javascript', 'cpp', 'c_sharp', 'ruby', 'go', 'typescript', 'php', 'kotlin', 'r', 'rust',
    'scala', 'elixir', 'haskell', 'perl'
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
