import re
import json
import requests
import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
from fastapi import HTTPException
import logging
from multiprocessing.pool import ThreadPool
import nltk
from nltk.corpus import stopwords

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_nltk():
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('corpora/stopwords')
        return True
    except LookupError:
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            return True
        except Exception as e:
            logger.warning(f"Failed to download NLTK data: {str(e)}")
            return False

NLTK_AVAILABLE = setup_nltk()

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

class AIAnalyzer:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3:8b"
        self.tech_keywords = [
            "python", "javascript", "react", "nodejs", "node.js", "java",
            "aws", "docker", "sql", "git", "agile", "typescript",
            "kubernetes", "mongodb", "express", "angular", "vue"
        ]
        self.stop_words = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'])
        if NLTK_AVAILABLE:
            try:
                self.stop_words = set(stopwords.words('english'))
            except:
                pass
        self.thread_pool = ThreadPool(processes=5)

    async def test_ollama_connection(self) -> bool:
        try:
            response = await asyncio.to_thread(
                requests.get, self.ollama_url.replace('/generate', '/tags'), timeout=2
            )
            if response.status_code == 200:
                models = response.json().get('models', [])
                return any('llama3' in model.get('name', '') for model in models)
            return False
        except Exception as e:
            logger.warning(f"Ollama connection test failed: {str(e)}")
            return False

    async def analyze_with_ollama(self, prompt: str, max_retries: int = 1) -> str:
        if len(prompt) < 200:  # Skip Ollama for short inputs
            logger.info("Short input, using fallback analysis")
            return self.fallback_analysis(prompt)
        
        if not await self.test_ollama_connection():
            logger.warning("Ollama not available, using fallback")
            return self.fallback_analysis(prompt)
        
        prompt = prompt[:500] + "..." if len(prompt) > 500 else prompt
        logger.info(f"Sending Ollama request (prompt length: {len(prompt)})");

        for attempt in range(max_retries + 1):
            try:
                response = await asyncio.to_thread(
                    requests.post,
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.8,
                            "num_predict": 64,  # Reduced for speed
                            "num_ctx": 256
                        }
                    },
                    timeout=5  # Reduced timeout
                )
                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get('response', '').strip()
                    logger.info(f"Ollama response length: {len(response_text)}")
                    return response_text
            except Exception as e:
                logger.warning(f"Ollama request failed (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries:
                await asyncio.sleep(0.5)
        
        logger.warning("Ollama failed, using fallback")
        return self.fallback_analysis(prompt)

    def fallback_analysis(self, prompt: str) -> str:
        logger.info("Using fallback analysis")
        try:
            if "keyword" in prompt.lower():
                return self._fallback_keyword_analysis(prompt)
            elif "bullet" in prompt.lower() or "improve" in prompt.lower():
                return self._fallback_bullet_analysis(prompt)
            return "No analysis available"
        except Exception as e:
            logger.error(f"Fallback analysis error: {str(e)}")
            return "Analysis failed"

    def _fallback_keyword_analysis(self, prompt: str) -> str:
        try:
            job_match = re.search(r"JOB:?\s*(.*?)(?:RESUME:|$)", prompt, re.DOTALL | re.IGNORECASE)
            resume_match = re.search(r"RESUME:?\s*(.*?)$", prompt, re.DOTALL | re.IGNORECASE)
            
            job_desc = job_match.group(1).strip().lower()[:200] if job_match else ""
            resume_text = resume_match.group(1).strip().lower()[:200] if resume_match else ""
            
            if not job_desc:
                return "None|low|0|No job description provided"
            
            missing_keywords = []
            for keyword in self.tech_keywords:
                if keyword.lower() in job_desc and keyword.lower() not in resume_text:
                    freq = job_desc.count(keyword.lower())
                    importance = "high" if freq > 2 else "medium" if freq > 1 else "low"
                    missing_keywords.append(f"{keyword}|{importance}|{freq}|Required skill")
            
            return "\n".join(missing_keywords[:3]) or "None|low|0|All key skills present"
        except Exception as e:
            logger.error(f"Fallback keyword analysis error: {str(e)}")
            return "Analysis error|low|0|Could not analyze keywords"

    def _fallback_bullet_analysis(self, prompt: str) -> str:
        try:
            exp_match = re.search(r"EXPERIENCE:?\s*(.*?)(?:JOB:|$)", prompt, re.DOTALL | re.IGNORECASE)
            experience = exp_match.group(1).strip()[:100] if exp_match else ""
            
            bullets = [line.lstrip('•- ').strip() for line in experience.split('\n') if line.strip() and (line.startswith('•') or line.startswith('-'))]
            
            if not bullets:
                return "ORIGINAL: Developed software\nIMPROVED: Developed scalable software solutions\nREASON: Added specificity\nIMPACT: 7"
            
            original = bullets[0]
            improved = f"Enhanced {original.lower()} with modern technologies"
            return f"ORIGINAL: {original}\nIMPROVED: {improved}\nREASON: Added impact\nIMPACT: 8"
        except Exception as e:
            logger.error(f"Fallback bullet analysis error: {str(e)}")
            return "ORIGINAL: Work experience\nIMPROVED: Delivered impactful work\nREASON: Added action verb\nIMPACT: 5"

    def parse_keywords(self, response: str) -> List[Keyword]:
        keywords = []
        if not response or response.strip() == "":
            return [Keyword("None", "low", 0, "No analysis available")]
        
        for line in response.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                try:
                    keyword = parts[0]
                    importance = parts[1].lower() if parts[1].lower() in ['high', 'medium', 'low'] else 'medium'
                    frequency = int(parts[2]) if parts[2].isdigit() else 1
                    context = parts[3] if len(parts) > 3 else f"{keyword} skill"
                    keywords.append(Keyword(keyword, importance, frequency, context))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing keyword: {str(e)}")
        
        return keywords or [Keyword("None", "low", 0, "No keywords identified")]

    def parse_improvements(self, response: str) -> List[BulletImprovement]:
        improvements = []
        if not response or response.strip() == "":
            return [BulletImprovement("No experience", "Enhanced experience", "Added language", 5)]
        
        sections = re.split(r'\n\s*\n|(?=ORIGINAL:)', response)
        for section in sections:
            if not section.strip():
                continue
            original = improved = reason = ""
            impact_score = 7
            for line in section.split('\n'):
                line = line.strip()
                if line.startswith('ORIGINAL:'):
                    original = line.replace('ORIGINAL:', '').strip()
                elif line.startswith('IMPROVED:'):
                    improved = line.replace('IMPROVED:', '').strip()
                elif line.startswith('REASON:'):
                    reason = line.replace('REASON:', '').strip()
                elif line.startswith('IMPACT:'):
                    impact_str = re.findall(r'\d+', line)
                    if impact_str:
                        impact_score = min(int(impact_str[0]), 10)
            if original and improved:
                improvements.append(BulletImprovement(original, improved, reason or "Enhanced impact", impact_score))
        
        return improvements or [BulletImprovement("Performed duties", "Delivered results", "Added specificity", 7)]

    async def extract_keywords_advanced(self, job_description: str, resume_text: str) -> List[Keyword]:
        try:
            prompt = f"Analyze job description for missing technical skills in resume.\nFormat: skill|importance|frequency|context\nJOB: {job_description[:200]}\nRESUME: {resume_text[:200]}"
            response = await self.analyze_with_ollama(prompt)
            return self.parse_keywords(response)
        except Exception as e:
            logger.error(f"Keyword extraction error: {str(e)}")
            return [Keyword("Analysis Error", "low", 0, "Could not analyze")]

    async def improve_bullets_advanced(self, resume_sections: Dict[str, str], job_description: str) -> List[BulletImprovement]:
        try:
            experience_text = resume_sections.get('experience', '')[:100] or "General work experience"
            prompt = (
                f"Improve resume bullet points for job requirements.\n"
                f"Format:\nORIGINAL: [text]\nIMPROVED: [text]\nREASON: [explanation]\nIMPACT: [1-10]\n\n"
                f"EXPERIENCE: {experience_text}\nJOB: {job_description[:100]}"
            )
            response = await self.analyze_with_ollama(prompt)
            return self.parse_improvements(response)
        except Exception as e:
            logger.error(f"Bullet improvement error: {str(e)}")
            return [BulletImprovement("Experience", "Enhanced experience", "Improved clarity", 6)]

    async def calculate_advanced_match_score(self, resume_text: str, keywords: List[Keyword], job_description: str) -> Dict[str, Any]:
        try:
            resume_lower = resume_text.lower()[:200]
            job_lower = job_description.lower()[:200]
            
            matched_keywords = 0
            total_weight = 0
            keyword_details = []
            
            for keyword in keywords:
                if keyword.keyword.lower() in ["none", "analysis error"]:
                    continue
                weight = {'high': 3, 'medium': 2, 'low': 1}.get(keyword.importance, 2) * keyword.frequency
                total_weight += weight
                is_matched = keyword.keyword.lower() in resume_lower
                if is_matched:
                    matched_keywords += weight
                keyword_details.append({
                    'keyword': keyword.keyword,
                    'matched': is_matched,
                    'importance': keyword.importance,
                    'weight': weight
                })
            
            keyword_score = int((matched_keywords / max(total_weight, 1)) * 100) if total_weight > 0 else 85
            quality_score = 50
            overall_score = int((keyword_score * 0.7) + (quality_score * 0.3))
            
            recommendations = [
                "Add relevant technical keywords from the job description",
                "Include quantifiable achievements"
            ]
            
            return {
                'overall_score': overall_score,
                'keyword_score': keyword_score,
                'quality_score': quality_score,
                'keyword_details': keyword_details,
                'recommendations': recommendations
            }
        except Exception as e:
            logger.error(f"Match score error: {str(e)}")
            return {
                'overall_score': 50,
                'keyword_score': 50,
                'quality_score': 50,
                'keyword_details': [],
                'recommendations': ["Error in analysis"]
            }