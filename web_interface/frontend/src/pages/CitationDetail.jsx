import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Container,
  Typography,
  Paper,
  Box,
  Button,
  Alert,
  CircularProgress,
  Chip,
  Card,
  CardContent,
  Divider,
  AppBar,
  Toolbar,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import FormatQuoteIcon from '@mui/icons-material/FormatQuote'
import FindInPageIcon from '@mui/icons-material/FindInPage'
import AssignmentIcon from '@mui/icons-material/Assignment'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

// Classification colors
const CLASSIFICATION_COLORS = {
  'SUPPORT': 'success',
  'CONTRADICT': 'error',
  'NOT_SUBSTANTIATE': 'warning',
  'OVERSIMPLIFY': 'warning',
  'IRRELEVANT': 'default',
  'MISQUOTE': 'error',
  'INDIRECT': 'default',
  'ETIQUETTE': 'default'
}

export default function CitationDetail() {
  const { sourceId, targetId } = useParams()
  const navigate = useNavigate()
  const [citation, setCitation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchCitation()
  }, [sourceId, targetId])

  const fetchCitation = async () => {
    try:
      setLoading(true)
      const response = await axios.get(`${API_BASE}/api/citations/${sourceId}/${targetId}`)
      setCitation(response.data)
      setError(null)
    } catch (err) {
      console.error('Error fetching citation:', err)
      setError('Failed to load citation details.')
    } finally {
      setLoading(false)
    }
  }

  const formatAuthors = (authors) => {
    if (!authors || authors.length === 0) return 'Unknown authors'
    if (authors.length <= 3) return authors.join(', ')
    return `${authors.slice(0, 3).join(', ')}, et al.`
  }

  const formatCitationString = (authors, year) => {
    if (!authors || authors.length === 0) return `Unknown (${year || 'N/A'})`
    const firstAuthor = authors[0]
    if (authors.length === 1) return `${firstAuthor} (${year})`
    if (authors.length === 2) return `${authors[0]} and ${authors[1]} (${year})`
    return `${firstAuthor} et al. (${year})`
  }

  const handleUserClassification = async (instanceId, classification) => {
    try {
      await axios.put(
        `${API_BASE}/api/citations/${sourceId}/${targetId}/classification?instance_id=${instanceId}&classification=${classification}`
      )
      // Refresh data
      fetchCitation()
    } catch (err) {
      console.error('Failed to update classification:', err)
    }
  }

  const handleUserComment = async (instanceId, comment) => {
    try {
      await axios.put(
        `${API_BASE}/api/citations/${sourceId}/${targetId}/comment?instance_id=${instanceId}&comment=${encodeURIComponent(comment)}`
      )
    } catch (err) {
      console.error('Failed to update comment:', err)
    }
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    )
  }

  if (error || !citation) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">{error || 'Citation not found'}</Alert>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/')}
          sx={{ mt: 2 }}
        >
          Back to List
        </Button>
      </Container>
    )
  }

  return (
    <Box sx={{ flexGrow: 1, bgcolor: 'background.default', minHeight: '100vh' }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/')}
            sx={{ mr: 2, color: 'white' }}
          >
            Back
          </Button>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Citation Detail
          </Typography>
          <Chip 
            label={`${citation.context_count} Context${citation.context_count !== 1 ? 's' : ''}`}
            color="secondary"
            variant="outlined"
          />
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        {/* Article Info Cards */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} md={6}>
            <Card elevation={3}>
              <CardContent>
                <Typography variant="overline" color="primary" fontWeight="bold">
                  📄 Citing Article
                </Typography>
                <Typography variant="h6" fontWeight="bold" sx={{ mt: 1 }}>
                  {citation.source.title || 'Untitled'}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  eLife.{citation.source.id}
                </Typography>
                {citation.source.authors && citation.source.authors.length > 0 && (
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    <strong>Authors:</strong> {formatAuthors(citation.source.authors)}
                  </Typography>
                )}
                <Typography variant="caption" color="text.secondary">
                  DOI: {citation.source.doi || 'N/A'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card elevation={3}>
              <CardContent>
                <Typography variant="overline" color="secondary" fontWeight="bold">
                  📚 Reference Article
                </Typography>
                <Typography variant="h6" fontWeight="bold" sx={{ mt: 1 }}>
                  {citation.target.title || 'Untitled'}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  eLife.{citation.target.id}
                </Typography>
                {citation.target.authors && citation.target.authors.length > 0 && (
                  <>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      <strong>Authors:</strong> {formatAuthors(citation.target.authors)}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                      <strong>Cited as:</strong> {formatCitationString(citation.target.authors, citation.target.date?.split('-')[0])}
                    </Typography>
                  </>
                )}
                <Typography variant="caption" color="text.secondary">
                  DOI: {citation.target.doi || 'N/A'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Citation Contexts */}
        <Paper elevation={3} sx={{ p: 3 }}>
          <Typography variant="h5" gutterBottom fontWeight="bold">
            Citation Contexts & Evidence
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Each context shows where the citing article references the target article,
            with LLM classification and evidence segments from the reference article.
          </Typography>

          {citation.contexts && citation.contexts.length > 0 ? (
            citation.contexts.map((context, index) => {
              const classification = context.classification || {}
              const llmCategory = classification.category
              const userCategory = classification.user_classification
              const justification = classification.justification
              const confidence = classification.confidence

              return (
                <Accordion key={index} sx={{ mb: 2 }}>
                  <AccordionSummary 
                    expandIcon={<ExpandMoreIcon />}
                    sx={{ 
                      '& .MuiAccordionSummary-content': { 
                        overflow: 'hidden',
                        pr: 2 
                      } 
                    }}
                  >
                    <Box sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 1.5, 
                      width: '100%',
                      minWidth: 0,
                      flexWrap: 'wrap'
                    }}>
                      <Box sx={{ display: 'flex', gap: 1, flexShrink: 0 }}>
                        <Chip 
                          label={`#${context.instance_id}`} 
                          size="small" 
                          color="primary"
                        />
                        {context.section && (
                          <Chip 
                            label={context.section} 
                            size="small" 
                            variant="outlined"
                          />
                        )}
                        {llmCategory && (
                          <Chip 
                            label={llmCategory}
                            size="small"
                            color={CLASSIFICATION_COLORS[llmCategory] || 'default'}
                          />
                        )}
                      </Box>
                      <Typography 
                        variant="body2" 
                        sx={{ 
                          flexGrow: 1,
                          minWidth: 0,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}
                      >
                        {context.context_text?.substring(0, 80)}...
                      </Typography>
                      <Chip 
                        label={`${context.evidence_segments?.length || 0} evidence`}
                        size="small"
                        color="secondary"
                        variant="outlined"
                        sx={{ flexShrink: 0 }}
                      />
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    {/* LLM Classification Card */}
                    {llmCategory && (
                      <Paper variant="outlined" sx={{ p: 2, mb: 3, bgcolor: 'info.50' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                          <AssignmentIcon color="info" />
                          <Typography variant="subtitle1" fontWeight="bold">
                            LLM Classification
                          </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 2, mb: 1 }}>
                          <Chip 
                            label={llmCategory}
                            color={CLASSIFICATION_COLORS[llmCategory] || 'default'}
                          />
                          {confidence && (
                            <Chip 
                              label={`Confidence: ${(confidence * 100).toFixed(0)}%`}
                              variant="outlined"
                            />
                          )}
                        </Box>
                        {justification && (
                          <Typography variant="body2" sx={{ mt: 1 }}>
                            {justification}
                          </Typography>
                        )}

                        {/* User Override */}
                        <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
                          <FormControl size="small" sx={{ minWidth: 200 }}>
                            <InputLabel>Your Classification</InputLabel>
                            <Select
                              value={userCategory || ''}
                              label="Your Classification"
                              onChange={(e) => handleUserClassification(context.instance_id, e.target.value)}
                            >
                              <MenuItem value="">Same as LLM</MenuItem>
                              <MenuItem value="SUPPORT">SUPPORT</MenuItem>
                              <MenuItem value="CONTRADICT">CONTRADICT</MenuItem>
                              <MenuItem value="NOT_SUBSTANTIATE">NOT_SUBSTANTIATE</MenuItem>
                              <MenuItem value="OVERSIMPLIFY">OVERSIMPLIFY</MenuItem>
                              <MenuItem value="IRRELEVANT">IRRELEVANT</MenuItem>
                              <MenuItem value="MISQUOTE">MISQUOTE</MenuItem>
                              <MenuItem value="INDIRECT">INDIRECT</MenuItem>
                              <MenuItem value="ETIQUETTE">ETIQUETTE</MenuItem>
                            </Select>
                          </FormControl>
                          {userCategory && userCategory !== llmCategory && (
                            <Alert severity="warning" sx={{ flex: 1 }}>
                              Your classification differs from LLM: {llmCategory} → {userCategory}
                            </Alert>
                          )}
                        </Box>

                        {/* User Comment */}
                        <TextField
                          fullWidth
                          multiline
                          rows={2}
                          label="Your Notes"
                          placeholder="Add your comments about this classification..."
                          defaultValue={classification.user_comment || ''}
                          onBlur={(e) => handleUserComment(context.instance_id, e.target.value)}
                          sx={{ mt: 2 }}
                          size="small"
                        />
                      </Paper>
                    )}

                    {/* Citation Context */}
                    <Box sx={{ mb: 3 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <FormatQuoteIcon color="primary" />
                        <Typography variant="subtitle1" fontWeight="bold">
                          Citation Context
                        </Typography>
                        {context.section && (
                          <Chip label={context.section} size="small" variant="outlined" />
                        )}
                      </Box>
                      <Paper 
                        variant="outlined" 
                        sx={{ 
                          p: 2, 
                          bgcolor: 'primary.50',
                          borderLeft: 4,
                          borderColor: 'primary.main',
                          overflowWrap: 'break-word',
                          wordBreak: 'break-word'
                        }}
                      >
                        <Typography 
                          variant="body1" 
                          sx={{ 
                            fontStyle: 'italic', 
                            lineHeight: 1.8,
                            whiteSpace: 'pre-wrap'
                          }}
                        >
                          {context.context_text}
                        </Typography>
                      </Paper>
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    {/* Evidence Segments */}
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <FindInPageIcon color="secondary" />
                        <Typography variant="subtitle1" fontWeight="bold">
                          Evidence from Reference Article
                        </Typography>
                        <Chip 
                          label={`${context.evidence_segments?.length || 0} segment${context.evidence_segments?.length !== 1 ? 's' : ''}`}
                          size="small"
                          color="secondary"
                        />
                      </Box>

                      {context.evidence_segments && context.evidence_segments.length > 0 ? (
                        context.evidence_segments.map((evidence, evidenceIndex) => (
                          <Paper
                            key={evidenceIndex}
                            variant="outlined"
                            sx={{
                              p: 2,
                              mb: 2,
                              bgcolor: 'secondary.50',
                              borderLeft: 4,
                              borderColor: 'secondary.main',
                              overflowWrap: 'break-word',
                              wordBreak: 'break-word'
                            }}
                          >
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1, flexWrap: 'wrap', gap: 1 }}>
                              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                {evidence.section && (
                                  <Chip label={evidence.section} size="small" variant="outlined" />
                                )}
                                <Chip 
                                  label={`Similarity: ${(evidence.similarity_score * 100).toFixed(1)}%`}
                                  size="small"
                                  color={evidence.similarity_score > 0.8 ? 'success' : evidence.similarity_score > 0.6 ? 'warning' : 'default'}
                                />
                              </Box>
                            </Box>
                            <Typography 
                              variant="body2" 
                              sx={{ 
                                lineHeight: 1.8,
                                whiteSpace: 'pre-wrap'
                              }}
                            >
                              {evidence.text}
                            </Typography>
                          </Paper>
                        ))
                      ) : (
                        <Alert severity="info">
                          No evidence segments available for this context.
                        </Alert>
                      )}
                    </Box>
                  </AccordionDetails>
                </Accordion>
              )
            })
          ) : (
            <Alert severity="warning">No citation contexts available.</Alert>
          )}
        </Paper>
      </Container>
    </Box>
  )
}
