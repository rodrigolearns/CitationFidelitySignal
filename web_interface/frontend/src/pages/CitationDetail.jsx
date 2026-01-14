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
  Grid,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import FormatQuoteIcon from '@mui/icons-material/FormatQuote'
import FindInPageIcon from '@mui/icons-material/FindInPage'
import AssignmentIcon from '@mui/icons-material/Assignment'
import VerifiedIcon from '@mui/icons-material/Verified'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WarningIcon from '@mui/icons-material/Warning'
import ErrorIcon from '@mui/icons-material/Error'
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
    try {
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
            sx={{ 
              color: 'white',
              borderColor: 'white',
              '& .MuiChip-label': { color: 'white' }
            }}
            variant="outlined"
          />
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        {/* Multi-Context Summary Card */}
        {citation.second_round_summary && 
         citation.second_round_summary.has_second_round && 
         citation.second_round_summary.total_contexts > 1 && (
          <Alert 
            severity={
              citation.second_round_summary.worst_recommendation === 'MISREPRESENTATION' ? 'error' :
              citation.second_round_summary.worst_recommendation === 'NEEDS_REVIEW' ? 'warning' :
              'success'
            }
            icon={
              citation.second_round_summary.worst_recommendation === 'MISREPRESENTATION' ? <ErrorIcon /> :
              citation.second_round_summary.worst_recommendation === 'NEEDS_REVIEW' ? <WarningIcon /> :
              <CheckCircleIcon />
            }
            sx={{ mb: 3 }}
          >
            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              📊 Multi-Context Citation Analysis
            </Typography>
            <Typography variant="body2" gutterBottom>
              This paper cites the reference <strong>{citation.second_round_summary.total_contexts} times</strong> in different sections. 
              Second-round verification was performed on <strong>{citation.second_round_summary.contexts_with_second_round}</strong> context{citation.second_round_summary.contexts_with_second_round !== 1 ? 's' : ''}.
            </Typography>
            
            <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {citation.second_round_summary.accurate_count > 0 && (
                <Chip 
                  label={`${citation.second_round_summary.accurate_count} Accurate`}
                  color="success"
                  size="small"
                />
              )}
              {citation.second_round_summary.needs_review_count > 0 && (
                <Chip 
                  label={`${citation.second_round_summary.needs_review_count} Need Review`}
                  color="warning"
                  size="small"
                />
              )}
              {citation.second_round_summary.misrepresentation_count > 0 && (
                <Chip 
                  label={`${citation.second_round_summary.misrepresentation_count} Misrepresentation`}
                  color="error"
                  size="small"
                />
              )}
              {citation.second_round_summary.corrected_count > 0 && (
                <Chip 
                  label={`${citation.second_round_summary.corrected_count} Corrected by 2nd Round`}
                  variant="outlined"
                  size="small"
                />
              )}
              {citation.second_round_summary.confirmed_count > 0 && (
                <Chip 
                  label={`${citation.second_round_summary.confirmed_count} Confirmed`}
                  variant="outlined"
                  size="small"
                  color="success"
                />
              )}
            </Box>
            
            {citation.second_round_summary.worst_user_overview && (
              <Box sx={{ mt: 2, p: 1.5, bgcolor: 'background.paper', borderRadius: 1 }}>
                <Typography variant="body2" fontWeight="medium" gutterBottom>
                  Most Concerning Issue (Context #{citation.second_round_summary.worst_instance_id}, {citation.second_round_summary.worst_section}):
                </Typography>
                <Typography variant="body2" sx={{ fontStyle: 'italic' }}>
                  "{citation.second_round_summary.worst_user_overview}"
                </Typography>
              </Box>
            )}
          </Alert>
        )}

        {/* Article Info Cards */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} md={6} sx={{ display: 'flex' }}>
            <Card 
              elevation={3}
              onClick={() => window.open(`https://elifesciences.org/articles/${citation.source.id}`, '_blank')}
              sx={{ 
                cursor: 'pointer',
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 6
                }
              }}
            >
              <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <Typography variant="overline" color="primary" fontWeight="bold">
                  📄 Citing Article (Click to view on eLife)
                </Typography>
                <Typography variant="h6" fontWeight="bold" sx={{ mt: 1, mb: 1 }}>
                  {citation.source.title || 'Untitled'}
                </Typography>
                {citation.source.authors && citation.source.authors.length > 0 && (
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    <strong>Authors:</strong> {formatAuthors(citation.source.authors)}
                  </Typography>
                )}
                <Box sx={{ mt: 'auto', display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="body2" color="text.secondary">
                    eLife.{citation.source.id}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">•</Typography>
                <Typography variant="caption" color="text.secondary">
                  DOI: {citation.source.doi || 'N/A'}
                </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6} sx={{ display: 'flex' }}>
            <Card 
              elevation={3}
              onClick={() => window.open(`https://elifesciences.org/articles/${citation.target.id}`, '_blank')}
              sx={{ 
                cursor: 'pointer',
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 6
                }
              }}
            >
              <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <Typography variant="overline" color="secondary" fontWeight="bold">
                  📚 Reference Article (Click to view on eLife)
                </Typography>
                <Typography variant="h6" fontWeight="bold" sx={{ mt: 1, mb: 1 }}>
                  {citation.target.title || 'Untitled'}
                </Typography>
                {citation.target.authors && citation.target.authors.length > 0 && (
                  <>
                    <Typography variant="body2" sx={{ mb: 0.5 }}>
                      <strong>Authors:</strong> {formatAuthors(citation.target.authors)}
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 1 }}>
                      <strong>Cited as:</strong> {formatCitationString(citation.target.authors, citation.target.date?.split('-')[0])}
                    </Typography>
                  </>
                )}
                <Box sx={{ mt: 'auto', display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="body2" color="text.secondary">
                    eLife.{citation.target.id}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">•</Typography>
                <Typography variant="caption" color="text.secondary">
                  DOI: {citation.target.doi || 'N/A'}
                </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Second-Round Verification Section */}
        {citation.contexts && citation.contexts.some(ctx => ctx.second_round) && (
          <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
            <Typography variant="h5" gutterBottom fontWeight="bold">
              Second-Round Verification
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              In-depth analysis with expanded evidence using GPT-4o for citations flagged as potentially problematic.
            </Typography>

            {citation.contexts.filter(ctx => ctx.second_round).map((context, index) => (
              <Box 
                key={index}
                sx={{ 
                  p: 2.5, 
                  mb: 3, 
                  bgcolor: context.second_round.recommendation === 'ACCURATE' 
                    ? 'success.50' 
                    : context.second_round.recommendation === 'MISREPRESENTATION'
                    ? 'error.50'
                    : 'warning.50',
                  borderLeft: 4,
                  borderColor: context.second_round.recommendation === 'ACCURATE'
                    ? 'success.main'
                    : context.second_round.recommendation === 'MISREPRESENTATION'
                    ? 'error.main'
                    : 'warning.main',
                  borderRadius: 1
                }}
              >
                {/* Header */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                  <Typography variant="h6" fontWeight="bold">
                    Context #{context.instance_id}
                  </Typography>
                  <Chip 
                    label={context.second_round.determination}
                    size="small"
                    color={context.second_round.determination === 'CORRECTED' ? 'warning' : 'default'}
                    variant="outlined"
                  />
                  <Chip 
                    label={context.second_round.category}
                    size="small"
                    color={CLASSIFICATION_COLORS[context.second_round.category] || 'default'}
                  />
                  <Chip 
                    label={`${(context.second_round.confidence * 100).toFixed(0)}%`}
                    size="small"
                    variant="outlined"
                  />
                </Box>
                
                {/* Verdict */}
                <Typography 
                  variant="body1" 
                  fontWeight="bold"
                  sx={{ 
                    mb: 2,
                    color: context.second_round.recommendation === 'ACCURATE' 
                      ? 'success.dark' 
                      : context.second_round.recommendation === 'MISREPRESENTATION'
                      ? 'error.dark'
                      : 'warning.dark'
                  }}
                >
                  {context.second_round.recommendation}: {context.second_round.user_overview || 'Second-round verification completed.'}
                </Typography>
                
                {/* Key findings */}
                {context.second_round.key_findings && context.second_round.key_findings.length > 0 && (
                  <>
                    <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1, mt: 1 }}>
                      Key Findings:
                    </Typography>
                    <Box component="ul" sx={{ m: 0, mb: 2, pl: 2.5 }}>
                      {context.second_round.key_findings.map((finding, i) => (
                        <li key={i}>
                          <Typography variant="body2" sx={{ lineHeight: 1.6 }}>
                            {finding}
                          </Typography>
                        </li>
                      ))}
                    </Box>
                  </>
                )}
                
                {/* Detailed explanation */}
                {context.second_round.detailed_explanation && (
                  <>
                    <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1, mt: 1 }}>
                      Detailed Analysis:
                    </Typography>
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        mb: 2,
                        lineHeight: 1.7,
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {context.second_round.detailed_explanation}
                    </Typography>
                  </>
                )}
                
                {/* Evidence quality metrics */}
                {context.second_round.evidence_quality && (
                  <>
                    <Typography variant="caption" fontWeight="bold" display="block" sx={{ mb: 1, mt: 1 }}>
                      Evidence Quality:
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                      <Chip 
                        label={`${(context.second_round.evidence_quality.quality_score * 100).toFixed(0)}%`}
                        size="small"
                        color={
                          context.second_round.evidence_quality.confidence_level === 'HIGH' 
                            ? 'success' 
                            : context.second_round.evidence_quality.confidence_level === 'MEDIUM'
                            ? 'warning'
                            : 'default'
                        }
                      />
                      <Chip 
                        label={`${context.second_round.evidence_quality.section_diversity} sections`}
                        size="small"
                        variant="outlined"
                      />
                      {context.second_round.evidence_quality.high_priority_segments > 0 && (
                        <Chip 
                          label={`${context.second_round.evidence_quality.high_priority_segments} Methods/Results`}
                          size="small"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </>
                )}
              </Box>
            ))}
          </Paper>
        )}

        {/* Citation Contexts & Evidence */}
        <Paper elevation={3} sx={{ p: 3 }}>
          <Typography variant="h5" gutterBottom fontWeight="bold">
            Citation Contexts & Evidence
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Each context shows where the citing article references the target article,
            with first-round LLM classification and evidence segments from the reference article.
          </Typography>

          {citation.contexts && citation.contexts.length > 0 ? (
            citation.contexts.map((context, index) => {
              const classification = context.classification || {}
              const llmCategory = classification.category
              const userCategory = classification.user_classification
              const justification = classification.justification
              const confidence = classification.confidence

              return (
                <Box key={index} sx={{ mb: 4, pb: 4, borderBottom: index < citation.contexts.length - 1 ? 1 : 0, borderColor: 'divider' }}>
                    {/* LLM Classification */}
                    {llmCategory && (
                      <Box sx={{ mb: 3 }}>
                        <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                          <AssignmentIcon color="info" fontSize="small" />
                          First-Round Classification
                          </Typography>
                        <Box sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
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
                        </Box>
                      </Box>
                    )}

                    {/* Citation Context */}
                    <Box sx={{ mb: 3 }}>
                      <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <FormatQuoteIcon color="primary" fontSize="small" />
                        Citation Context #{context.instance_id}
                        </Typography>
                      <Box 
                        sx={{ 
                          p: 2, 
                          bgcolor: 'grey.50',
                          borderLeft: 3,
                          borderColor: 'primary.main',
                          borderRadius: 1
                        }}
                      >
                        <Typography 
                          variant="body2" 
                          sx={{ 
                            fontStyle: 'italic', 
                            lineHeight: 1.7,
                            whiteSpace: 'pre-wrap'
                          }}
                        >
                          {context.context_text}
                        </Typography>
                      </Box>
                    </Box>

                    {/* Evidence Segments */}
                    <Box sx={{ mt: 3 }}>
                      <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <FindInPageIcon color="secondary" fontSize="small" />
                        Evidence from Reference ({context.evidence_segments?.length || 0} segments)
                        </Typography>

                      {context.evidence_segments && context.evidence_segments.length > 0 ? (
                        context.evidence_segments.map((evidence, evidenceIndex) => (
                          <Box
                            key={evidenceIndex}
                            sx={{
                              p: 1.5,
                              mb: 1.5,
                              bgcolor: 'grey.50',
                              borderLeft: 3,
                              borderColor: 'secondary.main',
                              borderRadius: 1
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
                                lineHeight: 1.6,
                                whiteSpace: 'pre-wrap'
                              }}
                            >
                              {evidence.text}
                            </Typography>
                          </Box>
                        ))
                      ) : (
                        <Alert severity="info">
                          No evidence segments available for this context.
                        </Alert>
                      )}
                    </Box>
                </Box>
              )
            })
          ) : (
            <Alert severity="warning">No citation contexts available.</Alert>
          )}
        </Paper>

        {/* Your Review Section */}
        <Paper elevation={3} sx={{ p: 3 }}>
          <Typography variant="h5" gutterBottom fontWeight="bold">
            Your Review
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Override the AI classification or add your notes for each citation context.
          </Typography>

          {citation.contexts && citation.contexts.map((context, index) => {
            const classification = context.classification || {}
            const llmCategory = classification.category
            const userCategory = classification.user_classification

            return (
              <Box key={index} sx={{ mb: 3, pb: 3, borderBottom: index < citation.contexts.length - 1 ? 1 : 0, borderColor: 'divider' }}>
                <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 2 }}>
                  Context #{context.instance_id} {context.section && `(${context.section})`}
                </Typography>
                
                <Grid container spacing={2}>
                  <Grid item xs={12} md={4}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Your Classification</InputLabel>
                      <Select
                        value={userCategory || ''}
                        label="Your Classification"
                        onChange={(e) => handleUserClassification(context.instance_id, e.target.value)}
                      >
                        <MenuItem value="">Same as AI</MenuItem>
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
                      <Typography variant="caption" color="warning.main" sx={{ mt: 0.5, display: 'block' }}>
                        Your classification differs from AI: {llmCategory} → {userCategory}
                      </Typography>
                    )}
                  </Grid>
                  
                  <Grid item xs={12} md={8}>
                    <TextField
                      fullWidth
                      multiline
                      rows={2}
                      label="Your Notes"
                      placeholder="Add your comments about this classification..."
                      defaultValue={classification.user_comment || ''}
                      onBlur={(e) => handleUserComment(context.instance_id, e.target.value)}
                      size="small"
                    />
                  </Grid>
                </Grid>
              </Box>
            )
          })}
        </Paper>
      </Container>
    </Box>
  )
}
