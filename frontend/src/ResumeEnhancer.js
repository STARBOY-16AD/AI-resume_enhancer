import React, { useState, useCallback } from 'react';
import './ResumeEnhancer.css';

const ResumeEnhancer = () => {
    const [step, setStep] = useState(1);
    const [resumeFile, setResumeFile] = useState(null);
    const [resumeText, setResumeText] = useState('');
    const [jobDescription, setJobDescription] = useState('');
    const [analysis, setAnalysis] = useState(null);
    const [enhancedResume, setEnhancedResume] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [progress, setProgress] = useState('');

    const normalizeText = (text) => {
        return text
            .replace(/^[•-]\s*/, '')
            .replace(/\s+/g, ' ')
            .trim();
    };

    const handleFileChange = (e) => {
        setResumeFile(e.target.files[0]);
        setError('');
        console.log('Selected file:', e.target.files[0]?.name);
    };

    const handleUpload = async () => {
        if (!resumeFile) {
            setError('Please select a resume file');
            console.error('No resume file selected');
            return;
        }

        console.log('Uploading file:', resumeFile.name);
        const formData = new FormData();
        formData.append('file', resumeFile);

        setLoading(true);
        setError('');
        setProgress('Uploading file...');

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {
                controller.abort();
                setError('Upload timed out. Try a smaller file or check your connection.');
            }, 15000); // Reduced to 15s for faster feedback

            const response = await fetch('/api/upload-resume', {
                method: 'POST',
                body: formData,
                signal: controller.signal,
            });

            clearTimeout(timeoutId);
            console.log('Upload status:', response.status);
            const data = await response.json();

            if (!response.ok) throw new Error(data.detail || 'Failed to upload resume');

            const { task_id } = data;
            setProgress('Processing file...');
            await pollForUploadResults(task_id);
        } catch (err) {
            const errorMsg = err.name === 'AbortError' ? 'Upload timed out' : `Upload error: ${err.message}`;
            setError(errorMsg);
            console.error(errorMsg);
            setProgress('');
            setLoading(false);
        }
    };

    const pollForUploadResults = async (taskId) => {
        const maxAttempts = 20; // 100s max (5s intervals)
        let attempts = 0;

        const poll = async () => {
            try {
                attempts++;
                setProgress(`Processing... (${Math.floor(attempts * 5 / 60)} min ${(attempts * 5) % 60} sec)`);

                const response = await fetch(`/api/upload-status/${taskId}`);
                if (!response.ok) throw new Error('Failed to check upload status');

                const result = await response.json();
                console.log('Upload status:', result.status);

                if (result.status === 'completed') {
                    setResumeText(result.result.text);
                    setStep(2);
                    setLoading(false);
                    setProgress('');
                } else if (result.status === 'failed') {
                    throw new Error(result.error || 'Upload processing failed');
                } else if (attempts >= maxAttempts) {
                    throw new Error('Upload processing timed out after 100 seconds');
                } else {
                    setTimeout(poll, 5000);
                }
            } catch (err) {
                setError(`Upload error: ${err.message}`);
                setProgress('');
                setLoading(false);
                console.error('Upload polling error:', err);
            }
        };

        setTimeout(poll, 2000);
    };

    const handleAnalysisStandard = async () => {
        if (!jobDescription.trim()) {
            setError('Please enter a job description');
            console.error('Empty job description');
            return;
        }
        if (resumeText.length > 10000) {
            setError('Resume text too long. Shorten to <10000 chars.');
            console.error('Resume text length:', resumeText.length);
            return;
        }
        if (resumeText.length < 50) {
            setError('Resume too short. Please upload a more detailed resume.');
            console.error('Resume text length:', resumeText.length);
            return;
        }

        console.log('Analyzing resume:', resumeText.slice(0, 200), '...');
        setLoading(true);
        setError('');
        setProgress('Starting analysis...');

        try {
            const formData = new FormData();
            formData.append('resume_text', resumeText);
            formData.append('job_description', jobDescription);

            const controller = new AbortController();
            const timeoutId = setTimeout(() => {
                controller.abort();
                setProgress('Analysis timed out - trying async method...');
            }, 10000); // Reduced to 10s for short resumes

            setProgress('Analyzing content...');

            const response = await fetch('/api/analyze-resume', {
                method: 'POST',
                body: formData,
                signal: controller.signal,
            });

            clearTimeout(timeoutId);
            console.log('Analysis status:', response.status);

            if (response.status === 408) throw new Error('TIMEOUT');

            const data = await response.json();
            console.log('Analysis data:', JSON.stringify(data, null, 2));

            if (!response.ok) throw new Error(data.detail || 'Failed to analyze resume');

            setAnalysis(data);
            setStep(3);
            setProgress('');
        } catch (err) {
            if (err.name === 'AbortError' || err.message === 'TIMEOUT') {
                console.log('Falling back to async analysis');
                await handleAnalysisAsync();
                return;
            }
            const errorMsg = `Analysis error: ${err.message}`;
            setError(errorMsg);
            setProgress('');
            console.error(errorMsg);
            setLoading(false);
        }
    };

    const handleAnalysisAsync = async () => {
        try {
            setProgress('Starting background analysis...');

            const formData = new FormData();
            formData.append('resume_text', resumeText);
            formData.append('job_description', jobDescription);

            const response = await fetch('/api/analyze-resume-async', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) throw new Error('Failed to start analysis');

            const { task_id } = await response.json();
            console.log('Started async analysis with task ID:', task_id);

            setProgress('Analysis started...');
            await pollForAnalysisResults(task_id);
        } catch (err) {
            const errorMsg = `Async analysis error: ${err.message}`;
            setError(errorMsg);
            setProgress('');
            console.error(errorMsg);
            setLoading(false);
        }
    };

    const pollForAnalysisResults = async (taskId) => {
        const maxAttempts = 20; // 100s max
        let attempts = 0;

        const poll = async () => {
            try {
                attempts++;
                setProgress(`Analyzing... (${Math.floor(attempts * 5 / 60)} min ${(attempts * 5) % 60} sec)`);

                const response = await fetch(`/api/analysis-status/${taskId}`);
                if (!response.ok) throw new Error('Failed to check analysis status');

                const result = await response.json();
                console.log('Analysis status:', result.status);

                if (result.status === 'completed') {
                    setAnalysis(result.result);
                    setStep(3);
                    setLoading(false);
                    setProgress('');
                } else if (result.status === 'failed') {
                    throw new Error(result.error || 'Analysis failed');
                } else if (attempts >= maxAttempts) {
                    throw new Error('Analysis timed out after 100 seconds');
                } else {
                    setTimeout(poll, 5000);
                }
            } catch (err) {
                setError(`Analysis error: ${err.message}`);
                setProgress('');
                setLoading(false);
                console.error('Analysis polling error:', err);
            }
        };

        setTimeout(poll, 2000);
    };

    const handleAnalysis = useCallback(async () => {
        await handleAnalysisStandard();
    }, [resumeText, jobDescription]);

    const handleGenerateResume = async () => {
        console.log('Generating resume');
        setLoading(true);
        setError('');
        setProgress('Generating enhanced resume...');

        try {
            if (!analysis?.improved_bullets || analysis.improved_bullets.length === 0) {
                throw new Error('No bullet point improvements available.');
            }

            const normalizedImprovements = analysis.improved_bullets.map(bullet => ({
                original: normalizeText(bullet.original),
                improved: normalizeText(bullet.improved),
                reason: bullet.reason,
                impact_score: bullet.impact_score
            }));

            console.log('Improvements:', JSON.stringify(normalizedImprovements, null, 2));

            const formData = new FormData();
            formData.append('original_text', resumeText);
            formData.append('improvements', JSON.stringify(normalizedImprovements));

            const response = await fetch('/api/generate-enhanced-resume', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to generate resume');
            }

            const enhancedText = await response.text();
            console.log('Enhanced resume:', enhancedText.slice(0, 300));

            setEnhancedResume(enhancedText);
            setStep(4);
        } catch (err) {
            const errorMsg = err.message.includes('No bullet points could be replaced')
                ? `${err.message} Ensure your resume matches the analysis bullets.`
                : `Generate error: ${err.message}`;
            setError(errorMsg);
            console.error(errorMsg);
        } finally {
            setLoading(false);
            setProgress('');
        }
    };

    const handleDownload = () => {
        const blob = new Blob([enhancedResume], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'enhanced_resume.txt';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        console.log('Downloaded resume');
    };

    const handleRestart = () => {
        setStep(1);
        setResumeFile(null);
        setResumeText('');
        setJobDescription('');
        setAnalysis(null);
        setEnhancedResume('');
        setError('');
        setProgress('');
    };

    return (
        <div className="resume-enhancer">
            <h1>Enhanced Resume</h1>

            {step === 1 && (
                <div className="step step-1">
                    <h2>Step 1: Upload Resume</h2>
                    <input 
                        type="file" 
                        accept=".pdf,.docx,.doc" 
                        onChange={handleFileChange}
                        disabled={loading}
                    />
                    {resumeFile && (
                        <p>Selected file: {resumeFile.name}</p>
                    )}
                    <button onClick={handleUpload} disabled={loading || !resumeFile}>
                        {loading ? 'Uploading...' : 'Upload Resume'}
                    </button>
                    {progress && <p className="progress">{progress}</p>}
                    {error && <p className="error">{error}</p>}
                </div>
            )}

            {step === 2 && (
                <div className="step step-2">
                    <h2>Step 2: Enter Job Description</h2>
                    <div className="resume-preview">
                        <h3>Resume Preview:</h3>
                        <div className="text-preview">
                            <pre>{resumeText.slice(0, 200)}{resumeText.length > 200 ? '...' : ''}</pre>
                        </div>
                        <p>Characters: {resumeText.length}/10000</p>
                    </div>
                    <div className="job-description-input">
                        <h3>Job Description:</h3>
                        <textarea
                            value={jobDescription}
                            onChange={(e) => setJobDescription(e.target.value)}
                            placeholder="Paste job description..."
                            rows={8}
                            disabled={loading}
                        />
                    </div>
                    <div className="button-group">
                        <button onClick={() => setStep(1)} disabled={loading}>
                            Back
                        </button>
                        <button onClick={handleAnalysis} disabled={loading || !jobDescription.trim()}>
                            {loading ? 'Analyzing...' : 'Analyze Resume'}
                        </button>
                    </div>
                    {progress && <p className="progress">{progress}</p>}
                    {error && <p className="error">{error}</p>}
                </div>
            )}

            {step === 3 && analysis && (
                <div className="step step-3">
                    <h2>Step 3: Review Analysis</h2>
                    <div className="analysis-results">
                        <div className="match-score">
                            <h3>Match Score: {analysis.match_score}%</h3>
                        </div>
                        {analysis.missing_keywords && analysis.missing_keywords.length > 0 && (
                            <div className="missing-keywords">
                                <h4>Missing Keywords:</h4>
                                <ul>
                                    {analysis.missing_keywords.map((kw, idx) => (
                                        <li key={idx}>
                                            <strong>{kw.keyword}</strong> - Importance: {kw.importance}
                                            {kw.context && <br />}<em>{kw.context}</em>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        {analysis.improved_bullets && analysis.improved_bullets.length > 0 && (
                            <div className="improved-bullets">
                                <h4>Bullet Improvements:</h4>
                                <ul>
                                    {analysis.improved_bullets.map((bullet, idx) => (
                                        <li key={idx} className="bullet-improvement">
                                            <div className="original">
                                                <strong>Original:</strong> {bullet.original}
                                            </div>
                                            <div className="improved">
                                                <strong>Improved:</strong> {bullet.improved}
                                            </div>
                                            <div className="reason">
                                                <strong>Reason:</strong> {bullet.reason}
                                            </div>
                                            {bullet.impact_score && (
                                                <div className="impact-score">
                                                    <strong>Impact:</strong> {bullet.impact_score}/100
                                                </div>
                                            )}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        {analysis.suggestions && analysis.suggestions.length > 0 && (
                            <div className="suggestions">
                                <h4>Suggestions:</h4>
                                <ul>
                                    {analysis.suggestions.map((suggestion, idx) => (
                                        <li key={idx}>{suggestion}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                    <div className="button-group">
                        <button onClick={() => setStep(2)} disabled={loading}>
                            Back
                        </button>
                        <button onClick={handleGenerateResume} disabled={loading || !analysis.improved_bullets.length}>
                            {loading ? 'Generating...' : 'Generate Enhanced Resume'}
                        </button>
                    </div>
                    {error && <p className="error">{error}</p>}
                </div>
            )}

            {step === 4 && (
                <div className="step step-4">
                    <h2>Step 4: Download Enhanced Resume</h2>
                    <p>Your enhanced resume is ready!</p>
                    <div className="enhanced-resume-preview">
                        <h3>Preview:</h3>
                        <div className="text-preview">
                            <pre>{enhancedResume.slice(0, 200)}{enhancedResume.length > 200 ? '...' : ''}</pre>
                        </div>
                    </div>
                    <div className="button-group">
                        <button onClick={handleDownload} disabled={loading}>
                            Download Enhanced Resume
                        </button>
                        <button onClick={handleRestart} disabled={loading}>
                            Start Over
                        </button>
                    </div>
                    {error && <p className="error">{error}</p>}
                </div>
            )}
        </div>
    );
};

export default ResumeEnhancer;