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
import WarningIcon from '@mui/icons-material/Warning'
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
  'EVAL_FAILED': { color: 'error', label: 'EVAL_FAILED ⚠️' },
  'INCOMPLETE_REFERENCE_DATA': { color: 'default', label: 'INCOMPLETE DATA 📄' },
  'UNCLASSIFIED': { color: 'default', label: 'Not Classified ⚪' }
}

export default function CitationList() {
  const navigate = useNavigate()
  const [citations, setCitations] = useState([])
  const [filteredCitations, setFilteredCitations] = useState([])
  const [stats, setStats] = useState(null)
  const [problematicPapers, setProblematicPapers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Filters
  const [classificationFilter, setClassificationFilter] = useState([]) // Changed to array for multiselect
  const [reviewFilter, setReviewFilter] = useState('ALL')
  const [showOnlySecondRound, setShowOnlySecondRound] = useState(true) // Default to showing only second-round citations

  useEffect(() => {
    fetchData()
  }, [])

  useEffect(() => {
    applyFilters()
  }, [citations, classificationFilter, reviewFilter, showOnlySecondRound])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [citationsRes, statsRes, problematicRes] = await Promise.all([
        axios.get(`${API_BASE}/api/citations`),
        axios.get(`${API_BASE}/api/stats`),
        axios.get(`${API_BASE}/api/problematic-papers`)
      ])
      
      setCitations(citationsRes.data.citations)
      setStats(statsRes.data)
      setProblematicPapers(problematicRes.data)
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

    // Second-round filter (default: only show citations with fidelity determination)
    if (showOnlySecondRound) {
      filtered = filtered.filter(c => c.second_round_summary && c.second_round_summary.has_second_round)
    }

    // Classification filter (multiselect)
    if (classificationFilter.length > 0) {
      filtered = filtered.filter(c => {
        const classification = c.classification || 'UNCLASSIFIED'
        return classificationFilter.includes(classification)
      })
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
      headerName: 'Initial Classification',
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
      field: 'second_round_summary',
      headerName: 'Fidelity Determination',
      width: 280,
      renderCell: (params) => {
        const summary = params.value
        
        // No second-round data
        if (!summary || !summary.has_second_round) {
          return (
            <Typography variant="caption" color="text.secondary">
              —
            </Typography>
          )
        }
        
        const { 
          worst_recommendation, 
          worst_category, 
          contexts_with_second_round, 
          total_contexts,
          misrepresentation_count,
          needs_review_count 
        } = summary
        
        // Color coding by recommendation
        const recommendationColors = {
          'ACCURATE': 'success',
          'NEEDS_REVIEW': 'warning',
          'MISREPRESENTATION': 'error'
        }
        
        const recommendationIcons = {
          'ACCURATE': '✓',
          'NEEDS_REVIEW': '⚠',
          'MISREPRESENTATION': '⛔'
        }
        
        const categoryLabel = CLASSIFICATION_COLORS[worst_category]?.label.split(' ')[0] || worst_category
        
        return (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, width: '100%' }}>
            {/* Main classification chip */}
            <Chip 
              label={`${categoryLabel} ${recommendationIcons[worst_recommendation] || '?'}`}
              color={recommendationColors[worst_recommendation] || 'default'}
              size="small"
              sx={{ fontWeight: 'bold' }}
            />
            
            {/* Context count badge */}
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
              {contexts_with_second_round} of {total_contexts} context{total_contexts !== 1 ? 's' : ''} verified
            </Typography>
            
            {/* Warning if multiple concerning contexts */}
            {(misrepresentation_count > 1 || needs_review_count > 1) && (
              <Chip 
                label={`Multiple issues (${misrepresentation_count + needs_review_count})`}
                size="small"
                color="error"
                variant="outlined"
                icon={<WarningIcon />}
                sx={{ fontSize: '0.65rem', height: '20px' }}
              />
            )}
          </Box>
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
                sx={{ 
                  color: 'white',
                  borderColor: 'white',
                  '& .MuiChip-label': { color: 'white' }
                }}
                variant="outlined"
              />
              <Chip 
                label={`${stats.classified_citations || 0} Classified`} 
                sx={{ 
                  color: 'white',
                  borderColor: 'white',
                  '& .MuiChip-label': { color: 'white' }
                }}
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

        {/* Problematic Papers Summary */}
        {problematicPapers.length > 0 && (
          <Paper elevation={3} sx={{ p: 3, mb: 3, bgcolor: '#fff3e0' }}>
            <Typography variant="h5" fontWeight="bold" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <WarningIcon color="warning" />
              Problematic Papers (Repeat Offenders)
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Papers with ≥2 problematic citations (NOT_SUBSTANTIATE, CONTRADICT, or MISQUOTE). Click any row to view detailed breakdown.
            </Typography>
            
            {/* Scrollable table container - fixed height to show ~10 rows */}
            <Box sx={{ 
              width: '100%', 
              maxHeight: '520px',  // Header (48px) + 10 rows × 47px each ≈ 520px
              overflowY: 'auto',
              overflowX: 'auto',
              border: '1px solid #ddd',
              borderRadius: '4px'
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead style={{ position: 'sticky', top: 0, zIndex: 1, backgroundColor: '#f5f5f5' }}>
                  <tr style={{ borderBottom: '2px solid #ddd' }}>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 'bold' }}>Rank</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 'bold' }}>eLife ID</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 'bold', minWidth: '300px' }}>Title</th>
                    <th style={{ padding: '12px', textAlign: 'left', fontWeight: 'bold' }}>Authors</th>
                    <th style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold' }}>Problematic Citations</th>
                  </tr>
                </thead>
                <tbody>
                  {problematicPapers.map((paper, idx) => (
                    <tr 
                      key={paper.article_id} 
                      style={{ 
                        borderBottom: '1px solid #eee',
                        cursor: 'pointer',
                        backgroundColor: 'white'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#fff8e1'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'white'}
                      onClick={() => {
                        navigate(`/problematic-paper/${paper.article_id}`)
                      }}
                    >
                      <td style={{ padding: '12px' }}>{idx + 1}</td>
                      <td style={{ padding: '12px' }}>
                        <Typography variant="body2" fontFamily="monospace">
                          eLife.{paper.article_id}
                        </Typography>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <Typography variant="body2" sx={{ 
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {paper.title}
                        </Typography>
                      </td>
                      <td style={{ padding: '12px' }}>
                        <Typography variant="body2" color="text.secondary">
                          {paper.authors && paper.authors.length > 0 
                            ? `${paper.authors[0]} et al.` 
                            : 'N/A'}
                        </Typography>
                      </td>
                      <td style={{ padding: '12px', textAlign: 'center' }}>
                        <Chip 
                          label={paper.problematic_count}
                          color="error"
                          size="small"
                          sx={{ fontWeight: 'bold' }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Box>
            
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2, textAlign: 'center' }}>
              Showing all {problematicPapers.length} problematic papers • Scroll to see more
            </Typography>
          </Paper>
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

            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={showOnlySecondRound}
                    onChange={(e) => setShowOnlySecondRound(e.target.checked)}
                  />
                }
                label="Show only with Fidelity Determination"
              />
              
              <FormControl size="small" sx={{ minWidth: 250 }}>
                <InputLabel>Filter Classifications</InputLabel>
                <Select
                  multiple
                  value={classificationFilter}
                  label="Filter Classifications"
                  onChange={(e) => setClassificationFilter(e.target.value)}
                  renderValue={(selected) => 
                    selected.length === 0 
                      ? 'All Classifications' 
                      : `${selected.length} selected`
                  }
                >
                  <MenuItem value="SUPPORT">
                    <Checkbox checked={classificationFilter.includes('SUPPORT')} />
                    ✅ SUPPORT
                  </MenuItem>
                  <MenuItem value="CONTRADICT">
                    <Checkbox checked={classificationFilter.includes('CONTRADICT')} />
                    🔴 CONTRADICT
                  </MenuItem>
                  <MenuItem value="NOT_SUBSTANTIATE">
                    <Checkbox checked={classificationFilter.includes('NOT_SUBSTANTIATE')} />
                    🟠 NOT_SUBSTANTIATE
                  </MenuItem>
                  <MenuItem value="OVERSIMPLIFY">
                    <Checkbox checked={classificationFilter.includes('OVERSIMPLIFY')} />
                    🟠 OVERSIMPLIFY
                  </MenuItem>
                  <MenuItem value="IRRELEVANT">
                    <Checkbox checked={classificationFilter.includes('IRRELEVANT')} />
                    🟡 IRRELEVANT
                  </MenuItem>
                  <MenuItem value="MISQUOTE">
                    <Checkbox checked={classificationFilter.includes('MISQUOTE')} />
                    🔴 MISQUOTE
                  </MenuItem>
                  <MenuItem value="INDIRECT">
                    <Checkbox checked={classificationFilter.includes('INDIRECT')} />
                    🟡 INDIRECT
                  </MenuItem>
                  <MenuItem value="ETIQUETTE">
                    <Checkbox checked={classificationFilter.includes('ETIQUETTE')} />
                    🟡 ETIQUETTE
                  </MenuItem>
                  <MenuItem value="EVAL_FAILED">
                    <Checkbox checked={classificationFilter.includes('EVAL_FAILED')} />
                    ⚠️ EVAL_FAILED
                  </MenuItem>
                  <MenuItem value="INCOMPLETE_REFERENCE_DATA">
                    <Checkbox checked={classificationFilter.includes('INCOMPLETE_REFERENCE_DATA')} />
                    📄 INCOMPLETE DATA
                  </MenuItem>
                  <MenuItem value="UNCLASSIFIED">
                    <Checkbox checked={classificationFilter.includes('UNCLASSIFIED')} />
                    ⚪ Not Classified
                  </MenuItem>
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
              rowHeight={80}
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
