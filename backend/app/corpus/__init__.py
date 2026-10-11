from pathlib import Path

from .chunker import Chunk, build_chunks
from .index import Index
from .loader import Corpus, load_corpus

__all__ = ["Chunk", "Corpus", "Index", "build_corpus"]


def build_corpus(source_dir: Path | None = None) -> tuple[Corpus, Index]:
    """Load, chunk and index the rules. Runs in well under a second."""
    corpus = load_corpus(source_dir)
    build_chunks(corpus)
    return corpus, Index(corpus.chunks)
