"""
qa_agent.py
===========
The e₹ Bridge Regulatory Q&A Agent.

HOW IT WORKS:
=============
RAG (Retrieval Augmented Generation) without any external LLM:

1. RETRIEVAL
   TF-IDF similarity search over the RBI knowledge base (12 chunks).
   Finds the most relevant regulatory passages for the question.

2. ANSWER GENERATION
   WITHOUT Groq API key: Returns the retrieved passage with
     a structured answer template. Still very useful — directly
     cites RBI sources.
   WITH Groq API key (optional, free tier): Uses Llama 3.1 8B
     to generate a natural-language answer grounded in the retrieved
     passages. More conversational.

3. SOURCE CITATION
   Every answer cites its source (RBI circular, FEMA rules, etc.)
   so users can verify — important for regulatory trust.

OPTIONAL GROQ INTEGRATION:
===========================
Groq provides free API access to Llama 3.1. Get a free key at:
https://console.groq.com/keys

Set in .env: GROQ_API_KEY=gsk_...

If no key is set, the agent still works — it just returns
the retrieved passages directly instead of generating prose.

WHY THIS IS BETTER THAN CALLING AN EXTERNAL AI API:
===================================================
- The knowledge base is curated specifically for RBI regulations
- Answers always cite sources (no hallucination risk)
- Works offline / without internet
- RBI can audit exactly what the agent knows and says
- Can be updated by adding new RBI circulars to knowledge_base.py
"""

import re
import math
import os
from collections import Counter
from typing import Optional

from app.agent.knowledge_base import RBI_KNOWLEDGE_CHUNKS


class QAAgent:
    """
    Answers regulatory questions using RAG over the RBI knowledge base.

    Usage:
        agent = QAAgent()
        result = agent.answer("What is the LRS annual limit?")
    """

    def __init__(self):
        self._build_tfidf_index()
        self._groq_client = None
        self._init_groq()

    # ── TF-IDF index ──────────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return [w for w in text.split() if len(w) > 2]

    def _build_tfidf_index(self):
        self.corpus = []
        self.chunk_ids = []

        for chunk in RBI_KNOWLEDGE_CHUNKS:
            doc = chunk["topic"] + " " + chunk["content"]
            self.corpus.append(self._tokenize(doc))
            self.chunk_ids.append(chunk["id"])

        N = len(self.corpus)
        all_terms = set(t for doc in self.corpus for t in doc)
        self.idf = {}
        for term in all_terms:
            df = sum(1 for doc in self.corpus if term in doc)
            self.idf[term] = math.log((N + 1) / (df + 1)) + 1

        self.tfidf_vectors = []
        for doc in self.corpus:
            tf = Counter(doc)
            total = max(len(doc), 1)
            vec = {t: (c / total) * self.idf.get(t, 1.0) for t, c in tf.items()}
            self.tfidf_vectors.append(vec)

    def _query_vector(self, text: str) -> dict:
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        tf = Counter(tokens)
        total = len(tokens)
        return {t: (c / total) * self.idf.get(t, 0.5) for t, c in tf.items()}

    def _cosine_sim(self, va: dict, vb: dict) -> float:
        common = set(va) & set(vb)
        if not common:
            return 0.0
        dot = sum(va[t] * vb[t] for t in common)
        ma = math.sqrt(sum(v * v for v in va.values()))
        mb = math.sqrt(sum(v * v for v in vb.values()))
        return dot / (ma * mb) if ma and mb else 0.0

    def _retrieve(self, question: str, top_k: int = 3) -> list[dict]:
        """Retrieve top-k most relevant knowledge chunks."""
        qv = self._query_vector(question)
        scored = [
            (self.chunk_ids[i], self._cosine_sim(qv, self.tfidf_vectors[i]))
            for i in range(len(self.chunk_ids))
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        top_ids = [cid for cid, score in scored[:top_k] if score > 0.01]
        chunk_map = {c["id"]: c for c in RBI_KNOWLEDGE_CHUNKS}
        return [chunk_map[cid] for cid in top_ids if cid in chunk_map]

    # ── Optional Groq integration ─────────────────────────────────────────────

    def _init_groq(self):
        """Initialise Groq client if API key is available."""
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=groq_key)
            except ImportError:
                pass  # groq not installed — fall back to RAG-only

    def _generate_with_groq(self, question: str, context_chunks: list[dict]) -> Optional[str]:
        """Use Llama 3.1 via Groq to generate an answer from retrieved context."""
        if not self._groq_client:
            return None

        context = "\n\n".join(
            f"[Source: {c['source']}]\n{c['content']}"
            for c in context_chunks
        )

        system_prompt = (
            "You are the e₹ Bridge regulatory assistant. Answer questions about "
            "Indian remittances, FEMA regulations, LRS rules, and the e-Rupee CBDC. "
            "Answer ONLY using the provided context. Be concise (2-4 sentences). "
            "If the context doesn't cover the question, say so honestly."
        )

        user_msg = f"Context:\n{context}\n\nQuestion: {question}"

        try:
            completion = self._groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=200,
                temperature=0.2,
            )
            return completion.choices[0].message.content
        except Exception:
            return None

    # ── Template-based answer generation (no LLM) ────────────────────────────

    def _generate_from_retrieval(self, question: str, chunks: list[dict]) -> str:
        """Generate a structured answer directly from retrieved passages."""
        if not chunks:
            return (
                "I couldn't find specific information on this in my knowledge base. "
                "For authoritative answers, please refer to RBI's official portal at "
                "rbi.org.in or contact fintech@rbi.org.in."
            )

        # Use the top chunk's content as the basis
        top_chunk = chunks[0]
        content = top_chunk["content"]

        # Trim to a reasonable length
        sentences = content.split(". ")
        answer = ". ".join(sentences[:4])
        if not answer.endswith("."):
            answer += "."

        return answer

    # ── Main answer method ────────────────────────────────────────────────────

    def answer(
        self,
        question: str,
        conversation_context: Optional[list] = None,
    ) -> dict:
        """
        Answer a regulatory question using RAG.

        Args:
            question: User's question
            conversation_context: List of previous {role, content} dicts

        Returns:
            {
                "answer": "...",
                "sources": [...],
                "retrieved_chunks": [...],
                "generation_method": "groq_llm" | "rag_retrieval",
                "agent": "e₹ Regulatory Q&A Agent v1.0"
            }
        """
        if not question or not question.strip():
            return {
                "answer": "Please ask a question about FEMA codes, LRS limits, or the e-Rupee CBDC.",
                "sources": [],
                "retrieved_chunks": [],
                "generation_method": "none",
                "agent": "e₹ Regulatory Q&A Agent v1.0",
            }

        # Step 1: Retrieve relevant chunks
        chunks = self._retrieve(question, top_k=3)

        # Step 2: Generate answer
        groq_answer = self._generate_with_groq(question, chunks)

        if groq_answer:
            final_answer = groq_answer
            method = "groq_llm_llama3"
        else:
            final_answer = self._generate_from_retrieval(question, chunks)
            method = "rag_retrieval"

        # Step 3: Format sources
        sources = [
            {"id": c["id"], "topic": c["topic"], "source": c["source"]}
            for c in chunks
        ]

        # Step 4: Add a helpful footer if relevant
        footer = ""
        q_lower = question.lower()
        if any(w in q_lower for w in ["limit", "lrs", "how much", "maximum"]):
            footer = " [LRS limit: $250,000 per financial year per individual]"
        elif any(w in q_lower for w in ["code", "fema", "purpose"]):
            footer = " [View all FEMA codes: rbi.org.in]"

        return {
            "answer": final_answer + footer,
            "sources": sources,
            "top_chunk": chunks[0] if chunks else None,
            "generation_method": method,
            "groq_available": self._groq_client is not None,
            "agent": "e₹ Regulatory Q&A Agent v1.0",
        }
