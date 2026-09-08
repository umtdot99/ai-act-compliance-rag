import re, json
import numpy as np
from collections import Counter
from sentence_transformers import SentenceTransformer

k1 = 1.5
b = 0.75
k_rrf = 60

def tokenizer(text):
    
    tokens = re.findall(r"[a-z0-9]+", text.lower())

    return tokens

class Retriever:

    def __init__(self):
        with open("chunks.json", encoding="utf-8") as f:
            self.chunk = json.load(f)

        self.lookup = {c["ID"]: c["Body"] for c in self.chunk}

        self.model = SentenceTransformer("BAAI/bge-small-en-v1.5")

        body_list = []
        for i in self.chunk:
            body_list.append(i["Body"])

        self.embeddings = self.model.encode(body_list, normalize_embeddings=True)

        doc_tokens = []
        for body in body_list:
            result = tokenizer(body)
            doc_tokens.append(result)

        self.doc_lengths = []
        for doc in doc_tokens:
            self.doc_lengths.append(len(doc))

        self.avgdl = np.mean(self.doc_lengths).round(1)

        df = Counter()
        self.doc_tfs = []
        for doc in doc_tokens:
        
            self.doc_tfs.append(Counter(doc))
            df.update(set(doc))
        
        self.idf = {t: np.log(1+(len(doc_tokens) - df[t] + 0.5) / (df[t] + 0.5)) for t in df}

    
    def search_query(self, s, k = 5):
        
        embeddings_s = self.model.encode(s, normalize_embeddings=True)
    
        result = np.dot(self.embeddings, embeddings_s)
        scores = {}
        for c, i in zip(self.chunk, result):
            scores[c["ID"]] = float(i)
        
        top_k = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:k]
    
        return top_k

    def bm25_search(self, s, k = 5):

        token_s = tokenizer(s)
        scores = {}
    
        for i, v in enumerate(self.chunk):
    
            score = 0.0
            norm = k1 * (1 - b + b * self.doc_lengths[i]/self.avgdl)
    
            for t in token_s: 
                f = self.doc_tfs[i][t]
                if f == 0:
                    continue
    
                score += self.idf.get(t, 0) * (f * (k1+1)) / (f + norm)
            
            scores[v["ID"]] = score
    
        top_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:k]
    
    
        return top_scores

    def rrf(self, dense_list, bm25_list, k=5):
        
        fused = {}
        for lst in (dense_list, bm25_list):
            for r, item in enumerate(lst, start=1):
                cid = item[0]
                fused[cid] = fused.get(cid, 0) + 1/(k_rrf + r)
                
    
        return sorted(fused.items(), key=lambda x: x[1], reverse=True)[:k] 


    def search(self, q, k):
        
        dense = self.search_query(q, 10)
        bm25 = self.bm25_search(q, 10)
        return self.rrf(dense, bm25, k)

    def build_context(self, top_k_query):

        lines = []
        for cid, score in top_k_query:
            body = self.lookup[cid]
            lines.append(f"[Article {cid}] {body}")
    
        return "<context>\n" + "\n".join(lines) + "\n</context>"