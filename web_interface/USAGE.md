# 🎉 Web Interface is Running!

## ✅ Status

**Backend (FastAPI)**: ✅ Running on http://localhost:8000  
**Frontend (React)**: ✅ Running on http://localhost:3000  
**Neo4j Database**: ✅ Connected

## 🚀 Access the Application

**Open in your browser**: http://localhost:3000

## 📊 What You'll See

### Home Page (Citation List)
- Professional Material-UI DataGrid table
- 14 qualified citations from Sprint 4
- Shows: Citing article, Reference article, Context count
- **Click any row** to view full details

### Detail Page (Citation Context & Evidence)
- Full article metadata (both citing and reference)
- Expandable accordions for each citation instance
- **Citation Context**: 4-sentence window from citing article
- **Evidence Segments**: Retrieved passages from reference article
- Color-coded similarity scores (green >80%, yellow >70%)

## 🔍 API Endpoints

The backend API is also available:
- **Docs**: http://localhost:8000/docs
- **Stats**: http://localhost:8000/api/stats
- **Citations**: http://localhost:8000/api/citations
- **Detail**: http://localhost:8000/api/citations/{source}/{target}

## 🛑 Stop Servers

Check running terminals:
- Terminal 4: Backend (FastAPI)
- Terminal 5: Frontend (Vite)

Press `Ctrl+C` in each terminal to stop.

## 🔄 Restart

```bash
# Terminal 1 - Backend
cd web_interface/backend
python3 main.py

# Terminal 2 - Frontend
cd web_interface/frontend
npm run dev
```

## 📦 What Data is Shown

- **14 qualified citations** from test runs
- **60 total citation contexts** extracted
- Evidence segments with BM25 + semantic retrieval
- Similarity scores (threshold: 0.7)

## 💡 Next Steps

1. **Explore the interface** to assess data quality
2. **Check evidence segments** - are they relevant?
3. **Evaluate contexts** - are they captured correctly?
4. **Scale to 100 citations** if quality looks good
5. **Move to Sprint 5** for LLM classification
