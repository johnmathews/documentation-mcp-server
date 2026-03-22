# ONNX Runtime Migration

**Date:** 2026-03-22

## Motivation

The previous embedding implementation used `sentence-transformers`, which pulls in PyTorch as a transitive dependency. This caused:

- **8GB Docker images** (PyTorch + CUDA stubs + training infrastructure)
- **10+ minute build times** on CI
- Unnecessary bloat — we only need inference, not training

## Approach

Replaced `sentence-transformers` with a custom `OnnxEmbeddingFunction` in `src/docserver/embedding.py` that uses:

- **onnxruntime** — ONNX model inference (~17MB wheel, CPU-only)
- **tokenizers** — HuggingFace fast tokenizer (~5MB wheel)
- **huggingface-hub** — model file download from HuggingFace

The same `all-mpnet-base-v2` model is used (768 dimensions), just loaded via ONNX Runtime instead of PyTorch. The ONNX model file is downloaded from the official HuggingFace repo (`sentence-transformers/all-mpnet-base-v2`, path `onnx/model.onnx`).

## Implementation Details

- Custom `OnnxEmbeddingFunction` implements ChromaDB's `EmbeddingFunction` interface
- Mean pooling with attention mask weighting (same as sentence-transformers)
- L2 normalization for cosine similarity
- Batch processing (batch_size=32)
- Model files cached at `DOCSERVER_MODEL_DIR` or `~/.cache/docserver/onnx_models/all-mpnet-base-v2/`
- HuggingFace model revision pinned to `e8c3b32edf5434bc2275fc9bab85f82640a19130` for reproducibility
- CoreML execution provider explicitly excluded (slower than CPU for this workload)

## Dockerfile Changes

- Set `DOCSERVER_MODEL_DIR=/app/models` so model pre-download during build lands at a fixed path accessible by the runtime `docserver` user (avoids root vs non-root `Path.home()` mismatch)
- Added `.dockerignore` to exclude tests, docs, journal from the image

## Dependencies Changed

Removed:
- `sentence-transformers>=5.0.0,<6` (and transitive PyTorch)

Added:
- `onnxruntime>=1.17.0,<2`
- `tokenizers>=0.20.0`
- `huggingface-hub>=0.20.0`

## Trade-offs

- **Pro:** Docker image ~1GB vs ~8GB, build time ~2 min vs ~10 min
- **Pro:** ONNX files avoid pickle deserialization (safer than PyTorch .bin files)
- **Pro:** Inference speed comparable or better for this model size
- **Con:** Custom embedding function to maintain (vs sentence-transformers doing it for you)
- **Con:** No GPU acceleration without separate onnxruntime-gpu package (not needed for this workload)

## Future Considerations

- Quantized model variants (110MB vs 436MB) available at `onnx/model_quint8_avx2.onnx` for further image size reduction
- ChromaDB's built-in ONNX support only covers all-MiniLM-L6-v2 (384 dims), so the custom function is necessary for all-mpnet-base-v2
