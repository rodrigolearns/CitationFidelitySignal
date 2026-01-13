import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Typography,
  Paper,
  Box,
  Alert,
  CircularProgress,
  Chip,
  AppBar,
  Toolbar,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Checkbox,
  FormControlLabel
} from '@mui/material'
import { DataGrid } from '@mui/x-data-grid'
import ArticleIcon from '@mui/icons-material/Article'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

// Classification colors
const CLASSIFICATION_COLORS = {
  'SUPPORT': { color: 'success', label: 'SUPPORT ✅' },
  'CONTRADICT': { color: 'error', label: 'CONTRADICT 🔴' },
  'NOT_SUBSTANTIATE': { color: 'warning', label: 'NOT_SUBSTANTIATE 🟠' },
  'OVERSIMPLIFY': { color: 'warning', label: 'OVERSIMPLIFY 🟠' },
  'IRRELEVANT': { color: 'default', label: 'IRRELEVANT 🟡' },
  'MISQUOTE': { color: 'error', label: 'MISQUOTE 🔴' },
  'INDIRECT': { color: 'default', label: 'INDIRECT 🟡' },
  'ETIQUETTE': { color: 'default', label: 'ETIQUETTE 🟡' },
  'UNCLASSIFIED': { color: 'default', label: 'Not Classified ⚪' }
}

export default function CitationList() {
  const navigate = useNavigate()
  const [citations, setCitations] = useState([])
  const [filteredCitations, setFilteredCitations] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Filters
  const [classificationFilter, setClassificationFilter] = useState('ALL')
  const [reviewFilter, setReviewFilter] = useState('ALL')

  useEffect(() => {
    fetchData()
  }, [])

  useEffect(() => {
    applyFilters()
  }, [citations, classificationFilter, reviewFilter])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [citationsRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/citations`),
        axios.get(`${API_BASE}/api/stats`)
      ])
      
      setCitations(citationsRes.data.citations)
      setStats(statsRes.data)
      setError(null)
    } catch (err) {
      console.error('Error fetching data:', err)
      setError('Failed to load citations. Make sure the backend is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }

  const applyFilters = () => {
    let filtered = citations

    // Classification filter
    if (classificationFilter !== 'ALL') {
      filtered = filtered.filter(c => 
        c.classification === classificationFilter ||
        (!c.classification && classificationFilter === 'UNCLASSIFIED')
      )
    }

    // Review filter
    if (reviewFilter === 'REVIEWED') {
      filtered = filtered.filter(c => c.manually_reviewed)
    } else if (reviewFilter === 'UNREVIEWED') {
      filtered = filtered.filter(c => !c.manually_reviewed)
    }

    setFilteredCitations(filtered)
  }

  const handleReviewChange = async (sourceId, targetId, reviewed) => {
    try {
      await axios.put(`${API_BASE}/api/citations/${sourceId}/${targetId}/review-status?reviewed=${reviewed}`)
      // Update local state
      setCitations(prev => prev.map(c => 
        c.source_id === sourceId && c.target_id === targetId
          ? { ...c, manually_reviewed: reviewed }
          : c
      ))
    } catch (err) {
      console.error('Failed to update review status:', err)
    }
  }

  const columns = [
    {
      field: 'classification',
      headerName: 'Classification',
      width: 180,
      renderCell: (params) => {
        const classification = params.value || 'UNCLASSIFIED'
        const config = CLASSIFICATION_COLORS[classification] || CLASSIFICATION_COLORS['UNCLASSIFIED']
        return (
          <Chip 
            label={config.label}
            color={config.color}
            size="small"
            sx={{ fontWeight: 'bold' }}
          />
        )
      },
    },
    {
      field: 'source_title',
      headerName: 'Citing Article',
      flex: 2,
      renderCell: (params) => (
        <Box>
          <Typography variant="body2" fontWeight="bold" noWrap>
            {params.value || 'Untitled'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            eLife.{params.row.source_id} ({params.row.source_year || 'N/A'})
          </Typography>
        </Box>
      ),
    },
    {
      field: 'target_title',
      headerName: 'Reference Article',
      flex: 2,
      renderCell: (params) => (
        <Box>
          <Typography variant="body2" fontWeight="bold" noWrap>
            {params.value || 'Untitled'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            eLife.{params.row.target_id} ({params.row.target_year || 'N/A'})
          </Typography>
        </Box>
      ),
    },
    {
      field: 'context_count',
      headerName: 'Contexts',
      width: 90,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => (
        <Chip 
          label={params.value} 
          color="primary" 
          size="small" 
          variant="outlined"
        />
      ),
    },
    {
      field: 'manually_reviewed',
      headerName: 'Reviewed',
      width: 100,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => (
        <Checkbox
          checked={params.value || false}
          onChange={(e) => {
            e.stopPropagation()
            handleReviewChange(
              params.row.source_id,
              params.row.target_id,
              e.target.checked
            )
          }}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    },
  ]

  const rows = filteredCitations.map((citation, index) => ({
    id: index,
    ...citation,
  }))

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <ArticleIcon sx={{ mr: 2 }} />
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            eLife Citation Qualification Viewer
          </Typography>
          {stats && (
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Chip 
                label={`${stats.qualified_citations} Citations`} 
                color="secondary" 
                variant="outlined"
              />
              <Chip 
                label={`${stats.classified_citations || 0} Classified`} 
                color="secondary" 
                variant="outlined"
              />
            </Box>
          )}
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Paper elevation={3} sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box>
              <Typography variant="h5" fontWeight="bold">
                Qualified eLife→eLife Citations
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Click on any row to view citation contexts and evidence segments
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 2 }}>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel>Classification</InputLabel>
                <Select
                  value={classificationFilter}
                  label="Classification"
                  onChange={(e) => setClassificationFilter(e.target.value)}
                >
                  <MenuItem value="ALL">All Classifications</MenuItem>
                  <MenuItem value="SUPPORT">✅ SUPPORT</MenuItem>
                  <MenuItem value="CONTRADICT">🔴 CONTRADICT</MenuItem>
                  <MenuItem value="NOT_SUBSTANTIATE">🟠 NOT_SUBSTANTIATE</MenuItem>
                  <MenuItem value="OVERSIMPLIFY">🟠 OVERSIMPLIFY</MenuItem>
                  <MenuItem value="IRRELEVANT">🟡 IRRELEVANT</MenuItem>
                  <MenuItem value="MISQUOTE">🔴 MISQUOTE</MenuItem>
                  <MenuItem value="INDIRECT">🟡 INDIRECT</MenuItem>
                  <MenuItem value="ETIQUETTE">🟡 ETIQUETTE</MenuItem>
                  <MenuItem value="UNCLASSIFIED">⚪ Not Classified</MenuItem>
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel>Review Status</InputLabel>
                <Select
                  value={reviewFilter}
                  label="Review Status"
                  onChange={(e) => setReviewFilter(e.target.value)}
                >
                  <MenuItem value="ALL">All</MenuItem>
                  <MenuItem value="REVIEWED">Reviewed Only</MenuItem>
                  <MenuItem value="UNREVIEWED">Unreviewed Only</MenuItem>
                </Select>
              </FormControl>
            </Box>
          </Box>

          <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
            Showing {filteredCitations.length} of {citations.length} citations
          </Typography>

          <Box sx={{ height: 600, width: '100%' }}>
            <DataGrid
              rows={rows}
              columns={columns}
              pageSize={10}
              rowsPerPageOptions={[10, 25, 50]}
              disableSelectionOnClick
              disableRowSelectionOnClick
              disableColumnMenu
              onRowClick={(params) => {
                navigate(`/citation/${params.row.source_id}/${params.row.target_id}`)
              }}
              sx={{
                '& .MuiDataGrid-row': {
                  cursor: 'pointer',
                  '&:hover': {
                    backgroundColor: 'action.hover',
                  },
                },
                '& .MuiDataGrid-cell': {
                  py: 2,
                  cursor: 'pointer',
                  '&:focus': {
                    outline: 'none',
                  },
                  '&:focus-within': {
                    outline: 'none',
                  },
                },
                '& .MuiDataGrid-cell:focus-within': {
                  outline: 'none',
                },
              }}
            />
          </Box>
        </Paper>
      </Container>
    </Box>
  )
}
