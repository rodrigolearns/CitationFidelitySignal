# eLife Citation Qualification Viewer

Professional web interface for viewing citation qualification data from Neo4j.

## Architecture

**Backend**: FastAPI + Neo4j
**Frontend**: React + Material-UI + Vite

## Quick Start

### 1. Start Backend (Terminal 1)

```bash
cd web_interface/backend
pip3 install -r requirements.txt
python3 main.py
```

Backend runs at: http://localhost:8000
API docs: http://localhost:8000/docs

### 2. Start Frontend (Terminal 2)

```bash
cd web_interface/frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:3000

### 3. Open Browser

Navigate to: **http://localhost:3000**

## Features

### Citation List View
- Professional Material-UI DataGrid table
- Shows all qualified citations
- Metadata: citing article, reference article, context count
- Click any row to view details

### Citation Detail View
- Full citation context (4-sentence windows)
- Evidence segments from reference article
- Similarity scores (BM25 + semantic)
- Expandable accordions for each citation instance
- Color-coded similarity scores

## API Endpoints

- `GET /api/stats` - Overall statistics
- `GET /api/citations` - List all qualified citations
- `GET /api/citations/{source_id}/{target_id}` - Detailed citation data

## Requirements

**Backend**:
- Python 3.9+
- Neo4j running on bolt://localhost:7687

**Frontend**:
- Node.js 16+
- npm or yarn

## Development

Frontend uses Vite for fast hot-reload development.
Backend uses FastAPI with auto-reload enabled.

Both servers have CORS configured for local development.
