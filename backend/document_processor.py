import pdfplumber
import docx
import io
import re
from typing import Dict
from fastapi import HTTPException
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        self.section_keywords = {
            'experience': ['experience', 'work', 'employment', 'professional'],
            'skills': ['skills'],
            'education': ['education', 'degree', 'university', 'academic'],
            'summary': ['summary', 'contact', 'objective', 'profile']
        }
        # Precompile regex patterns
        self.space_regex = re.compile(r'\s+')
        self.char_regex = re.compile(r'[^\w\s\-\.,;@()]')
        self.replacements = {
            'ReactJS': 'React',
            'NodeJS': 'Node.js',
            'Javascript': 'JavaScript',
            'Node JS': 'Node.js',
            'REACT': 'React',
            'NODE': 'Node.js',
            'Typescript': 'TypeScript',
        }

    def extract_text_from_pdf(self, content: bytes) -> str:
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = ""
                # Process only first 2 pages to improve speed
                for page in pdf.pages[:2]:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
            logger.info(f"Extracted PDF text length: {len(text)} chars")
            if not text.strip():
                raise HTTPException(status_code=400, detail="Failed to extract text from PDF")
            return self.clean_text(text)
        except Exception as e:
            logger.error(f"PDF extraction error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error extracting PDF: {str(e)}")

    def extract_text_from_docx(self, content: bytes) -> str:
        try:
            doc = docx.Document(io.BytesIO(content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            logger.info(f"Extracted DOCX text length: {len(text)} chars")
            if not text.strip():
                raise HTTPException(status_code=400, detail="Failed to extract text from DOCX")
            return self.clean_text(text)
        except Exception as e:
            logger.error(f"DOCX extraction error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error extracting DOCX: {str(e)}")

    def clean_text(self, text: str) -> str:
        text = self.space_regex.sub(' ', text)
        text = self.char_regex.sub(' ', text)
        for old, new in self.replacements.items():
            text = text.replace(old, new)
        return text.strip()

    def parse_resume_sections(self, text: str) -> Dict[str, str]:
        sections = {k: '' for k in self.section_keywords}
        lines = text.split('\n')
        current_section = 'summary'

        for line in lines:
            line = line.strip()
            if not line:
                continue

            line_lower = line.lower()
            section_detected = False

            for section, keywords in self.section_keywords.items():
                if any(keyword in line_lower for keyword in keywords):
                    if len(line) < 60 and (line.isupper() or not re.search(r'[.!?]', line)):
                        current_section = section
                        section_detected = True
                        break

            if not section_detected:
                sections[current_section] += line + '\n'

        for section in sections:
            sections[section] = sections[section].strip()
        
        logger.info(f"Parsed sections: {list(sections.keys())}")
        return sections