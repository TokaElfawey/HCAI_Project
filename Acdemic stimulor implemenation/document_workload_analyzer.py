import hashlib
import io
import logging
import math
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class WorkloadAnalysis:
    filename: str
    word_count: int
    chunks: int
    topic_count: int
    diversity: float
    estimated_hours: int
    document_id: str
    stored_vectors: int
    extracted_text: str
    topics: list
    topic_similarity: list

    def to_dict(self):
        result = asdict(self)
        result.pop("extracted_text")
        return result


class DocumentWorkloadAnalyzer:
    """Extract course material, group its topics, and estimate study time."""

    def __init__(
        self,
        embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
        max_topics=8,
        chroma_path=None,
    ):
        if max_topics < 1:
            raise ValueError("max_topics must be at least 1.")
        self.embedding_model_name = embedding_model_name
        self.max_topics = max_topics
        self.chroma_path = Path(chroma_path) if chroma_path else Path(__file__).parent / "data" / "course_material_chroma"

    @staticmethod
    def _compute_device():
        import torch

        if torch.cuda.is_available():
            return "cuda"
        mps_backend = getattr(torch.backends, "mps", None)
        if mps_backend is not None and mps_backend.is_available():
            return "mps"
        xpu_backend = getattr(torch, "xpu", None)
        if xpu_backend is not None and xpu_backend.is_available():
            return "xpu"
        return "cpu"

    @staticmethod
    def _chunks(text, words_per_chunk=180):
        words = re.findall(r"\S+", text)
        return [
            " ".join(words[index:index + words_per_chunk])
            for index in range(0, len(words), words_per_chunk)
        ]

    @staticmethod
    def _study_hours(word_count, diversity):
        # Baseline: 1,000 words per study hour, scaled up by up to 100% for topic diversity.
        return max(1, math.ceil((word_count / 1000) * (1 + diversity)))

    @staticmethod
    def read_document_text(file_bytes, filename):
        if not isinstance(file_bytes, bytes) or not file_bytes:
            raise ValueError("The uploaded document is empty.")
        if Path(filename).suffix.lower() not in {".pdf", ".docx", ".pptx"}:
            raise ValueError("Upload a PDF, DOCX, or PPTX document.")

        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
            from docling.datamodel.pipeline_options import (
                PdfPipelineOptions,
                RapidOcrOptions,
                TesseractCliOcrOptions,
            )
            from docling.document_converter import DocumentConverter, DocumentStream, PdfFormatOption
        except ImportError as error:
            raise ImportError(
                "Document analysis requires Docling. Install it with "
                "'pip install docling'."
            ) from error

        download_exceptions = ()
        try:
            from rapidocr.utils.download_file import DownloadFileException
        except ImportError:
            pass
        else:
            download_exceptions = (DownloadFileException,)

        compute_device = DocumentWorkloadAnalyzer._compute_device()
        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = True
        pdf_options.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.AUTO)
        if compute_device == "cuda":
            pdf_options.ocr_options = RapidOcrOptions(backend="torch")
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
            }
        )
        source = DocumentStream(name=Path(filename).name, stream=io.BytesIO(file_bytes))
        try:
            document = converter.convert(source).document
        except download_exceptions as error:
            tesseract_path = shutil.which("tesseract")
            if tesseract_path is None:
                raise RuntimeError(
                    "RapidOCR could not download its OCR model, and Tesseract is not "
                    "installed. Check your network connection or install Tesseract."
                ) from error

            logging.getLogger(__name__).warning(
                "RapidOCR could not download its OCR model; retrying with local Tesseract."
            )
            pdf_options.ocr_options = TesseractCliOcrOptions(
                tesseract_cmd=tesseract_path
            )
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
                }
            )
            source = DocumentStream(
                name=Path(filename).name,
                stream=io.BytesIO(file_bytes),
            )
            document = converter.convert(source).document
        text = document.export_to_markdown()
        if not text.strip():
            raise ValueError("No readable text was found in the uploaded document.")
        return text

    @staticmethod
    def _load_chromadb():
        try:
            import chromadb
        except ImportError as error:
            raise ImportError(
                "Saving embeddings requires ChromaDB. Install it with "
                "'pip install chromadb'."
            ) from error
        return chromadb

    def _store_embeddings(self, document_id, filename, chunks, embeddings, labels):
        chromadb = self._load_chromadb()
        collection = chromadb.PersistentClient(path=str(self.chroma_path)).get_or_create_collection(
            name="course_materials",
            metadata={"hnsw:space": "cosine"},
        )
        collection.upsert(
            ids=[f"{document_id}:{index}" for index in range(len(chunks))],
            documents=chunks,
            embeddings=embeddings.tolist(),
            metadatas=[
                {
                    "document_id": document_id,
                    "filename": Path(filename).name,
                    "chunk_index": index,
                    "topic": int(labels[index]) + 1,
                }
                for index in range(len(chunks))
            ],
        )
        return len(chunks)

    def analyze(self, file_bytes, filename):
        if not isinstance(file_bytes, bytes) or not file_bytes:
            raise ValueError("The uploaded document is empty.")
        if Path(filename).suffix.lower() not in {".pdf", ".docx", ".pptx"}:
            raise ValueError("Upload a PDF, DOCX, or PPTX document.")
        self._load_chromadb()

        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer
            from sklearn.cluster import KMeans
        except ImportError as error:
            raise ImportError(
                "Workload analysis requires sentence-transformers, scikit-learn, "
                "and numpy. Install them with "
                "'pip install sentence-transformers scikit-learn numpy'."
            ) from error

        text = self.read_document_text(file_bytes, filename)
        chunks = self._chunks(text)
        if not chunks:
            raise ValueError("No readable text was found in the uploaded document.")

        embeddings = SentenceTransformer(
            self.embedding_model_name,
            device=self._compute_device(),
        ).encode(
            chunks,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        document_id = hashlib.sha256(file_bytes).hexdigest()
        topic_count = min(self.max_topics, max(1, int(math.sqrt(len(chunks)))))
        labels = KMeans(n_clusters=topic_count, random_state=42, n_init=10).fit_predict(embeddings)
        centers = np.asarray([
            embeddings[labels == topic].mean(axis=0)
            for topic in range(topic_count)
        ])
        center_norms = np.linalg.norm(centers, axis=1, keepdims=True)
        normalized_centers = centers / np.maximum(center_norms, 1e-12)
        similarity_matrix = np.clip(normalized_centers @ normalized_centers.T, -1.0, 1.0)

        topics = []
        for topic in range(topic_count):
            topic_indices = np.flatnonzero(labels == topic)
            topic_similarities = embeddings[topic_indices] @ normalized_centers[topic]
            representative_index = topic_indices[int(np.argmax(topic_similarities))]
            topics.append({
                "topic": topic + 1,
                "chunks": int(len(topic_indices)),
                "similarity": float(np.mean(topic_similarities)),
                "excerpt": chunks[representative_index][:240],
            })

        if topic_count > 1:
            upper_triangle = similarity_matrix[np.triu_indices(topic_count, k=1)]
            diversity = float(np.clip(1 - upper_triangle.mean(), 0.0, 1.0))
        else:
            diversity = 0.0
        word_count = len(re.findall(r"\b\w+\b", text))
        stored_vectors = self._store_embeddings(
            document_id,
            filename,
            chunks,
            embeddings,
            labels,
        )

        return WorkloadAnalysis(
            filename=Path(filename).name,
            word_count=word_count,
            chunks=len(chunks),
            topic_count=topic_count,
            diversity=diversity,
            estimated_hours=self._study_hours(word_count, diversity),
            document_id=document_id,
            stored_vectors=stored_vectors,
            extracted_text=text,
            topics=topics,
            topic_similarity=np.round(similarity_matrix, 3).tolist(),
        )
