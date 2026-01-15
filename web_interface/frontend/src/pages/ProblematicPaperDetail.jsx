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
  List,
  ListItem,
  ListItemText,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WarningIcon from '@mui/icons-material/Warning'
import ErrorIcon from '@mui/icons-material/Error'
import InfoIcon from '@mui/icons-material/Info'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

// Impact Assessment colors - matching the severity levels
const CLASSIFICATION_COLORS = {
  'CRITICAL_CONCERN': 'error',      // 🔴 Red - Most concerning
  'MODERATE_CONCERN': 'warning',    // 🟠 Orange - Moderate concern
  'MINOR_CONCERN': 'info',          // 🔵 Blue - Minor concern
  'FALSE_ALARM': 'success',         // 🟢 Green - No concern
  'NOT_PERFORMED': 'default',       // ⚪ Grey - Not analyzed
}

const CLASSIFICATION_ICONS = {
  'CRITICAL_CONCERN': <ErrorIcon />,
  'MODERATE_CONCERN': <WarningIcon />,
  'MINOR_CONCERN': <InfoIcon />,
  'FALSE_ALARM': <CheckCircleIcon />,
  'NOT_PERFORMED': <InfoIcon />,
}

export default function ProblematicPaperDetail() {
  const { article_id } = useParams()
  const navigate = useNavigate()
  
  const [paperData, setPaperData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState(null)
  const [analysisProgress, setAnalysisProgress] = useState([])
  const [analysisStage, setAnalysisStage] = useState('')

  useEffect(() => {
    fetchPaperData()
  }, [article_id])

  const fetchPaperData = async () => {
    try {
      setLoading(true)
      const response = await axios.get(`${API_BASE}/api/problematic-paper/${article_id}`)
      setPaperData(response.data)
      setError(null)
    } catch (err) {
      console.error('Error fetching paper data:', err)
      setError('Failed to load paper details.')
    } finally {
      setLoading(false)
    }
  }

  const triggerAnalysis = async () => {
    try {
      setAnalyzing(true)
      setAnalysisError(null)
      setAnalysisProgress([])
      setAnalysisStage('Initializing...')
      
      // Simulate progress updates
      const progressSteps = [
        { stage: 'Checking for cached XML...', delay: 500 },
        { stage: 'Downloading XML if needed...', delay: 3000 },
        { stage: 'Phase A: Deep reading citations (this takes ~1-2 minutes)...', delay: 5000 },
        { stage: 'Phase A: Analyzing citation patterns...', delay: 60000 },
        { stage: 'Phase B: Generating comprehensive report...', delay: 30000 },
        { stage: 'Finalizing and storing results...', delay: 5000 }
      ]
      
      let currentStep = 0
      const progressTimer = setInterval(() => {
        if (currentStep < progressSteps.length) {
          const step = progressSteps[currentStep]
          if (step) {
            setAnalysisStage(step.stage)
            setAnalysisProgress(prev => [...prev, {
              time: new Date().toLocaleTimeString(),
              message: step.stage
            }])
            currentStep++
          }
        } else {
          clearInterval(progressTimer)
        }
      }, 10000) // Update every 10 seconds
      
      // Start first step immediately
      setAnalysisStage(progressSteps[0].stage)
      setAnalysisProgress([{
        time: new Date().toLocaleTimeString(),
        message: 'Starting Workflow 5 analysis...'
      }])
      
      const response = await axios.post(`${API_BASE}/api/problematic-paper/${article_id}/analyze`, {}, {
        timeout: 600000 // 10 minute timeout
      })
      
      clearInterval(progressTimer)
      setAnalysisStage('Complete!')
      setAnalysisProgress(prev => [...prev, {
        time: new Date().toLocaleTimeString(),
        message: '✅ Analysis completed successfully!'
      }])
      
      // Refresh paper data to show new analysis
      await fetchPaperData()
      
      // Small delay to show completion message
      setTimeout(() => {
        alert('✅ Workflow 5 analysis completed successfully!')
      }, 500)
    } catch (err) {
      console.error('Error running analysis:', err)
      setAnalysisError(err.response?.data?.detail || 'Analysis failed. Please try again.')
      setAnalysisProgress(prev => [...prev, {
        time: new Date().toLocaleTimeString(),
        message: `❌ Error: ${err.response?.data?.detail || err.message}`
      }])
    } finally {
      setAnalyzing(false)
    }
  }

  const formatAuthors = (authors) => {
    if (!authors || authors.length === 0) return 'Unknown authors'
    if (authors.length <= 3) return authors.join(', ')
    return `${authors.slice(0, 3).join(', ')}, et al.`
  }

  const formatIntextCitation = (authors, year) => {
    if (!authors || authors.length === 0) return `(${year || 'n.d.'})`
    const firstAuthor = authors[0]
    if (authors.length === 1) {
      return `${firstAuthor}, ${year || 'n.d.'}`
    } else if (authors.length === 2) {
      return `${firstAuthor} and ${authors[1]}, ${year || 'n.d.'}`
    } else {
      return `${firstAuthor} et al., ${year || 'n.d.'}`
    }
  }

  // Get unique reference papers from problematic citations
  const getUniqueReferencePapers = () => {
    if (!paperData?.problematic_citations) return []
    
    const uniquePapers = new Map()
    paperData.problematic_citations.forEach(citation => {
      if (!uniquePapers.has(citation.target_id)) {
        // Extract in-text citation from the context if available
        let inTextCitation = null
        if (citation.context) {
          // Try to find the citation format in the context
          // Common patterns: "Author et al., YEAR" or "Author, YEAR" or "(Author et al., YEAR)"
          const citationMatch = citation.context.match(/([A-Z][a-z]+(?:\s+et\s+al\.)?(?:\s+and\s+[A-Z][a-z]+)?),?\s+(\d{4}[a-z]?)/);
          if (citationMatch) {
            inTextCitation = citationMatch[0]
          }
        }
        
        uniquePapers.set(citation.target_id, {
          target_id: citation.target_id,
          target_title: citation.target_title,
          target_authors: citation.target_authors,
          target_year: citation.target_year,
          in_text_citation: inTextCitation
        })
      }
    })
    return Array.from(uniquePapers.values())
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">{error}</Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/')} sx={{ mt: 2 }}>
          Back to List
        </Button>
      </Container>
    )
  }

  const impactAnalysis = paperData?.impact_analysis
  const hasAnalysis = impactAnalysis !== null

  return (
    <Box>
      {/* Header */}
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/')}
            sx={{ mr: 2 }}
          >
            Back
          </Button>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Problematic Paper Analysis
          </Typography>
          <Chip
            label={`eLife.${article_id}`}
            color="primary"
            variant="outlined"
            sx={{ fontFamily: 'monospace' }}
          />
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        
        {/* Paper Information */}
        <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
          <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            📄 Paper Information
          </Typography>
          <Divider sx={{ my: 2 }} />
          
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Typography variant="subtitle2" color="text.secondary">Title</Typography>
              <Typography variant="body1" fontWeight="medium">
                {paperData.title || 'Untitled'}
              </Typography>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" color="text.secondary">Authors</Typography>
              <Typography variant="body2">
                {formatAuthors(paperData.authors)}
              </Typography>
            </Grid>
            
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" color="text.secondary">DOI</Typography>
              <Typography variant="body2" fontFamily="monospace">
                {paperData.doi || 'N/A'}
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" color="text.secondary">Publication Year</Typography>
              <Typography variant="body2">
                {paperData.pub_year || 'N/A'}
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" color="text.secondary">Problematic Citations</Typography>
              <Typography variant="body2" fontWeight="bold" color="error.main">
                {paperData.problematic_citations?.length || 0} issues found
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                View Papers on eLife
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {/* Citing Article Button */}
                <Button
                  size="small"
                  variant="contained"
                  startIcon={<OpenInNewIcon />}
                  href={`https://elifesciences.org/articles/${article_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5, px: 1 }}
                >
                  Open Citing Article
                </Button>
                
                {/* Reference Paper Buttons */}
                {getUniqueReferencePapers().map((refPaper) => (
                  <Button
                    key={refPaper.target_id}
                    size="small"
                    variant="outlined"
                    startIcon={<OpenInNewIcon sx={{ fontSize: '0.9rem' }} />}
                    href={`https://elifesciences.org/articles/${refPaper.target_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    sx={{ textTransform: 'none', fontSize: '0.75rem', py: 0.5, px: 1 }}
                  >
                    {refPaper.in_text_citation || formatIntextCitation(refPaper.target_authors, refPaper.target_year)}
                  </Button>
                ))}
              </Box>
            </Grid>
          </Grid>
        </Paper>

        {/* Workflow 5 Impact Analysis */}
        {hasAnalysis ? (
          <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                🎯 Workflow 5: Impact Assessment
              </Typography>
              <Chip
                icon={CLASSIFICATION_ICONS[impactAnalysis.overall_classification]}
                label={impactAnalysis.overall_classification?.replace(/_/g, ' ')}
                color={CLASSIFICATION_COLORS[impactAnalysis.overall_classification]}
                sx={{ fontWeight: 'bold' }}
              />
            </Box>

            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
              Status: ✅ Complete | Analyzed: {paperData.analyzed_at ? new Date(paperData.analyzed_at).toLocaleString() : 'Unknown'}
            </Typography>

            <Divider sx={{ my: 2 }} />

            {/* Executive Summary */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                📝 Executive Summary
              </Typography>
              <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant="body1">
                  {impactAnalysis.phase_b_analysis?.executive_summary || 'No summary available.'}
                </Typography>
              </Paper>
            </Box>

            {/* Detailed Report */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="h6">📄 Detailed Report</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>
                  {impactAnalysis.phase_b_analysis?.detailed_report || 'No detailed report available.'}
                </Typography>
              </AccordionDetails>
            </Accordion>

            {/* Pattern Analysis */}
            {impactAnalysis.phase_b_analysis?.pattern_analysis && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">🔍 Pattern Analysis</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    {/* Section Distribution */}
                    {impactAnalysis.phase_b_analysis.pattern_analysis.section_distribution && (
                      <Grid item xs={12}>
                        <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                          Section Distribution
                        </Typography>
                        <List dense>
                          {Object.entries(impactAnalysis.phase_b_analysis.pattern_analysis.section_distribution).map(([section, count]) => (
                            <ListItem key={section}>
                              <ListItemText
                                primary={`${section}: ${count} citations`}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </Grid>
                    )}

                    {/* Severity Assessment */}
                    {impactAnalysis.phase_b_analysis.pattern_analysis.severity_assessment && (
                      <Grid item xs={12}>
                        <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                          Severity Assessment
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                          <Chip
                            label={`High: ${impactAnalysis.phase_b_analysis.pattern_analysis.severity_assessment.high_impact_citations?.length || 0}`}
                            color="error"
                            size="small"
                          />
                          <Chip
                            label={`Moderate: ${impactAnalysis.phase_b_analysis.pattern_analysis.severity_assessment.moderate_impact_citations?.length || 0}`}
                            color="warning"
                            size="small"
                          />
                          <Chip
                            label={`Low: ${impactAnalysis.phase_b_analysis.pattern_analysis.severity_assessment.low_impact_citations?.length || 0}`}
                            color="success"
                            size="small"
                          />
                        </Box>
                      </Grid>
                    )}
                  </Grid>
                </AccordionDetails>
              </Accordion>
            )}

            {/* Recommendations */}
            {impactAnalysis.phase_b_analysis?.recommendations && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">💡 Recommendations</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                        For Reviewers
                      </Typography>
                      <Typography variant="body2">
                        {impactAnalysis.phase_b_analysis.recommendations.for_reviewers}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                        For Readers
                      </Typography>
                      <Typography variant="body2">
                        {impactAnalysis.phase_b_analysis.recommendations.for_readers}
                      </Typography>
                    </Grid>
                    {impactAnalysis.phase_b_analysis.recommendations.for_authors && (
                      <Grid item xs={12}>
                        <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                          For Authors
                        </Typography>
                        <Typography variant="body2">
                          {impactAnalysis.phase_b_analysis.recommendations.for_authors}
                        </Typography>
                      </Grid>
                    )}
                  </Grid>
                </AccordionDetails>
              </Accordion>
            )}

            {/* Phase A Individual Assessments */}
            {impactAnalysis.phase_a_assessments && impactAnalysis.phase_a_assessments.length > 0 && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">📖 Phase A: Individual Citation Assessments</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {impactAnalysis.phase_a_assessments.map((assessment, idx) => {
                      // Find matching problematic citation to get author/year info
                      const citationNum = assessment.citation_id || idx + 1
                      const matchingCitation = paperData.problematic_citations?.[citationNum - 1]
                      const intextCitation = matchingCitation 
                        ? formatIntextCitation(matchingCitation.target_authors, matchingCitation.target_year)
                        : null
                      
                      return (
                        <Paper key={idx} variant="outlined" sx={{ p: 2 }}>
                          <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                            {intextCitation ? `${intextCitation} - Citation #${citationNum}` : `Citation #${citationNum}`}
                          </Typography>
                          <Chip
                            label={assessment.impact_assessment}
                            size="small"
                            color={
                              assessment.impact_assessment === 'HIGH_IMPACT' ? 'error' :
                              assessment.impact_assessment === 'MODERATE_IMPACT' ? 'warning' : 'success'
                            }
                            sx={{ mb: 1 }}
                          />
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            {assessment.validity_impact?.explanation || 'No explanation available.'}
                          </Typography>
                        </Paper>
                      )
                    })}
                  </Box>
                </AccordionDetails>
              </Accordion>
            )}
          </Paper>
        ) : (
          /* No Analysis Yet - Show Action Button */
          <Paper elevation={2} sx={{ p: 3, mb: 3, textAlign: 'center' }}>
            {!analyzing ? (
              <>
                <InfoIcon sx={{ fontSize: 60, color: 'info.main', mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Workflow 5 Analysis Not Yet Run
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Run Workflow 5: Impact Assessment to get a comprehensive analysis of how these miscitations
                  affect the paper's scientific validity. This includes deep reading of full papers, pattern
                  detection, and strategic recommendations.
                </Typography>
                
                {analysisError && (
                  <Alert severity="error" sx={{ mb: 2, textAlign: 'left' }}>
                    {analysisError}
                  </Alert>
                )}
                
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<PlayArrowIcon />}
                  onClick={triggerAnalysis}
                >
                  Run Workflow 5 Analysis
                </Button>
                
                <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 2 }}>
                  ⏱️ This analysis takes approximately 2-3 minutes with DeepSeek batching.
                  Cost: ~$0.08 per paper
                </Typography>
              </>
            ) : (
              /* Analysis Running - Show Progress */
              <Box>
                <CircularProgress size={60} sx={{ mb: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Running Workflow 5 Analysis
                </Typography>
                
                {/* Collapsible Progress Log */}
                <Accordion sx={{ mb: 2, boxShadow: 'none', border: '1px solid', borderColor: 'divider' }}>
                  <AccordionSummary 
                    expandIcon={<ExpandMoreIcon />}
                    sx={{ 
                      bgcolor: 'primary.light',
                      '&:hover': { bgcolor: 'primary.main' },
                      '& .MuiAccordionSummary-content': { my: 1 }
                    }}
                  >
                    <Typography variant="body1" color="primary.contrastText" sx={{ fontWeight: 'medium' }}>
                      {analysisStage}
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails sx={{ p: 0 }}>
                    <Paper variant="outlined" sx={{ 
                      p: 2, 
                      maxHeight: '200px',
                      overflowY: 'auto', 
                      textAlign: 'left',
                      bgcolor: 'grey.50',
                      fontFamily: 'monospace',
                      fontSize: '0.875rem',
                      borderRadius: 0,
                      border: 'none',
                      borderTop: '1px solid',
                      borderColor: 'divider'
                    }}>
                      {analysisProgress.map((log, idx) => (
                        <Box key={idx} sx={{ mb: 0.5 }}>
                          <Typography component="span" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                            [{log.time}]
                          </Typography>
                          {' '}
                          <Typography component="span" sx={{ fontSize: '0.875rem' }}>
                            {log.message}
                          </Typography>
                        </Box>
                      ))}
                    </Paper>
                  </AccordionDetails>
                </Accordion>
                
                <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 2 }}>
                  ⏱️ Please wait 2-3 minutes. Do not close this page.
                </Typography>
              </Box>
            )}
          </Paper>
        )}

        {/* Problematic Citations List */}
        <Paper elevation={2} sx={{ p: 3 }}>
          <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            ⚠️ Problematic Citations ({paperData.problematic_citations?.length || 0})
          </Typography>
          <Divider sx={{ my: 2 }} />

          {paperData.problematic_citations && paperData.problematic_citations.length > 0 ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {paperData.problematic_citations.map((citation, idx) => {
                const intextCitation = formatIntextCitation(citation.target_authors, citation.target_year)
                return (
                  <Accordion key={idx}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%', flexWrap: 'wrap' }}>
                        <Typography variant="subtitle1" fontWeight="bold">
                          {intextCitation} - Citation #{idx + 1}
                        </Typography>
                        <Chip
                          label={citation.classification}
                          size="small"
                          variant="outlined"
                          sx={{
                            borderColor: 'black',
                            color: 'black',
                            '& .MuiChip-label': {
                              color: 'black'
                            }
                          }}
                        />
                        <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            → eLife.{citation.target_id}
                          </Typography>
                          {citation.target_title && (
                            <Typography variant="caption" color="text.secondary" sx={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              ({citation.target_title})
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </AccordionSummary>
                  <AccordionDetails>
                    <Grid container spacing={2}>
                      <Grid item xs={12}>
                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                          Referenced Paper
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                          <Typography variant="body2" fontFamily="monospace">
                            eLife.{citation.target_id}
                          </Typography>
                          <Button
                            size="small"
                            variant="text"
                            startIcon={<OpenInNewIcon />}
                            href={`https://elifesciences.org/articles/${citation.target_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            sx={{ textTransform: 'none', minWidth: 'auto' }}
                          >
                            View on eLife
                          </Button>
                        </Box>
                        {citation.target_title && (
                          <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic', mb: 2 }}>
                            {citation.target_title}
                          </Typography>
                        )}
                      </Grid>

                      <Grid item xs={12}>
                        <Typography variant="subtitle2" color="text.secondary">
                          Citation Context
                        </Typography>
                        <Typography variant="body2">
                          {citation.context || 'No context available'}
                        </Typography>
                      </Grid>
                      
                      {citation.justification && (
                        <Grid item xs={12}>
                          <Typography variant="subtitle2" color="text.secondary">
                            Analysis
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {citation.justification}
                          </Typography>
                        </Grid>
                      )}

                      <Grid item xs={12}>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => navigate(`/citation/${article_id}/${citation.target_id}`)}
                        >
                          View Full Citation Details
                        </Button>
                      </Grid>
                    </Grid>
                  </AccordionDetails>
                </Accordion>
              )
            })}
            </Box>
          ) : (
            <Alert severity="info">No problematic citations found for this paper.</Alert>
          )}
        </Paper>

      </Container>
    </Box>
  )
}
