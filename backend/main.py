from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import io
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid
import logging
from document_processor import DocumentProcessor
from ai_analyzer import AIAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Resume Enhancer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@dataclass
class Keyword:
    keyword: str
    importance: str
    frequency: int
    context: str = ""

@dataclass
class BulletImprovement:
    original: str
    improved: str
    reason: str
    impact_score: int = 0

doc_processor = DocumentProcessor()
ai_analyzer = AIAnalyzer()

upload_results = {}
analysis_results = {}

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    logger.info(f"Received upload request for file: {file.filename}")
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if not file.filename.lower().endswith(('.pdf', '.docx', '.doc')):
        logger.error(f"Unsupported file type: {file.filename}")
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")
    
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        logger.error(f"File too large: {len(content)} bytes")
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")

    task_id = str(uuid.uuid4())
    upload_results[task_id] = {"status": "processing", "result": None}
    
    async def process_upload():
        try:
            if file.filename.lower().endswith('.pdf'):
                text = doc_processor.extract_text_from_pdf(content)
            else:
                text = doc_processor.extract_text_from_docx(content)
            
            if len(text) > 10000:
                logger.error(f"Extracted text too long: {len(text)} chars")
                raise HTTPException(status_code=400, detail="Resume text exceeds 10000 characters")
            
            if not text.strip():
                raise HTTPException(status_code=400, detail="Could not extract text from the uploaded file")
            
            sections = doc_processor.parse_resume_sections(text)
            
            upload_results[task_id] = {
                "status": "completed",
                "result": {
                    "filename": file.filename,
                    "text": text,
                    "sections": sections
                }
            }
        except Exception as e:
            logger.error(f"Upload processing error: {str(e)}")
            upload_results[task_id] = {"status": "failed", "error": str(e)}
    
    background_tasks.add_task(process_upload)
    return {"task_id": task_id, "status": "processing"}

@app.get("/api/upload-status/{task_id}")
async def get_upload_status(task_id: str):
    if task_id not in upload_results:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = upload_results[task_id]
    
    if result["status"] in ["completed", "failed"]:
        upload_results.pop(task_id, None)
    
    return result

@app.post("/api/analyze-resume")
async def analyze_resume(
    resume_text: str = Form(...),
    job_description: str = Form(...)
):
    if not resume_text.strip():
        logger.error("Resume text is empty")
        raise HTTPException(status_code=400, detail="Resume text cannot be empty")
    if not job_description.strip():
        logger.error("Job description is empty")
        raise HTTPException(status_code=400, detail="Job description cannot be empty")
    if len(resume_text) > 10000:
        logger.error(f"Resume text too long: {len(resume_text)} chars")
        raise HTTPException(status_code=400, detail="Resume text exceeds 10000 characters")
    
    try:
        async def perform_analysis():
            keywords = await ai_analyzer.extract_keywords_advanced(job_description, resume_text)
            match_score = await ai_analyzer.calculate_advanced_match_score(resume_text, keywords, job_description)
            improved_bullets = await ai_analyzer.improve_bullets_advanced(doc_processor.parse_resume_sections(resume_text), job_description)
            
            return keywords, match_score, improved_bullets
        
        try:
            keywords, match_score, improved_bullets = await asyncio.wait_for(
                perform_analysis(), 
                timeout=10.0  # Reduced timeout
            )
        except asyncio.TimeoutError:
            logger.error("Analysis timed out")
            raise HTTPException(status_code=408, detail="Analysis timed out. Try the async endpoint.")
        
        analysis = {
            "match_score": match_score['overall_score'],
            "missing_keywords": [
                {
                    "keyword": k.keyword,
                    "importance": k.importance,
                    "frequency": k.frequency,
                    "context": k.context
                } for k in keywords
            ],
            "improved_bullets": [
                {
                    "original": b.original,
                    "improved": b.improved,
                    "reason": b.reason,
                    "impact_score": b.impact_score
                } for b in improved_bullets
            ],
            "suggestions": match_score['recommendations']
        }
        
        return JSONResponse(content=analysis)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing resume: {str(e)}")

@app.post("/api/analyze-resume-async")
async def analyze_resume_async(
    background_tasks: BackgroundTasks,
    resume_text: str = Form(...),
    job_description: str = Form(...)
):
    task_id = str(uuid.uuid4())
    analysis_results[task_id] = {"status": "processing", "result": None}
    
    async def background_analysis():
        try:
            keywords = await ai_analyzer.extract_keywords_advanced(job_description, resume_text)
            match_score = await ai_analyzer.calculate_advanced_match_score(resume_text, keywords, job_description)
            improved_bullets = await ai_analyzer.improve_bullets_advanced(doc_processor.parse_resume_sections(resume_text), job_description)
            
            analysis = {
                "match_score": match_score['overall_score'],
                "missing_keywords": [{"keyword": k.keyword, "importance": k.importance, "frequency": k.frequency, "context": k.context} for k in keywords],
                "improved_bullets": [{"original": b.original, "improved": b.improved, "reason": b.reason, "impact_score": b.impact_score} for b in improved_bullets],
                "suggestions": match_score['recommendations']
            }
            
            analysis_results[task_id] = {"status": "completed", "result": analysis}
        except Exception as e:
            logger.error(f"Async analysis error: {str(e)}")
            analysis_results[task_id] = {"status": "failed", "error": str(e)}
    
    background_tasks.add_task(background_analysis)
    return {"task_id": task_id, "status": "processing"}

@app.get("/api/analysis-status/{task_id}")
async def get_analysis_status(task_id: str):
    if task_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = analysis_results[task_id]
    
    if result["status"] in ["completed", "failed"]:
        analysis_results.pop(task_id, None)
    
    return result

@app.post("/api/generate-enhanced-resume")
async def generate_enhanced_resume(
    original_text: str = Form(...),
    improvements: str = Form(...)
):
    logger.info("Generating enhanced resume")
    try:
        try:
            improvements_list = json.loads(improvements)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON format for improvements: {str(e)}")

        sections = doc_processor.parse_resume_sections(original_text)

        def normalize_text(text: str) -> str:
            return re.sub(r'^\s*[•-]\s*', '', text).strip().lower()

        enhanced_experience = sections.get('experience', '')
        replacements_made = False

        for improvement in improvements_list:
            original = normalize_text(improvement['original'])
            improved = improvement['improved'].strip()
            new_lines = []
            for line in enhanced_experience.split('\n'):
                normalized_line = normalize_text(line)
                if original == normalized_line:
                    new_lines.append(f"• {improved}")
                    replacements_made = True
                else:
                    new_lines.append(line)
            
            enhanced_experience = '\n'.join(new_lines)

        if not replacements_made:
            logger.warning("No bullet points were replaced")
            raise HTTPException(status_code=400, detail="No bullet points could be replaced. Ensure improvements match resume content.")

        enhanced_resume = f"Enhanced Resume\n{'=' * 50}\n"
        if sections.get('summary'):
            enhanced_resume += f"Summary\n{'-' * 30}\n{sections['summary']}\n\n"
        if enhanced_experience:
            enhanced_resume += f"Experience\n{'-' * 30}\n{enhanced_experience}\n\n"
        if sections.get('skills'):
            enhanced_resume += f"Skills\n{'-' * 30}\n{sections['skills']}\n\n"
        if sections.get('education'):
            enhanced_resume += f"Education\n{'-' * 30}\n{sections['education']}\n\n"
        enhanced_resume += f"{'=' * 50}\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        def generate():
            yield enhanced_resume

        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=enhanced_resume.txt"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate resume error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating enhanced resume: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "Resume Enhancer API is running"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Resume Enhancer API...")
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=30)