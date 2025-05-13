import streamlit as st
import random
from typing import Dict, List, Any
import os
import json
import io
import base64
import re
import docx
import PyPDF2
from io import BytesIO
import pandas as pd
from together import Together  # Make sure you install this package: pip install together
from dotenv import load_dotenv
load_dotenv()
def extract_text_from_pdf(file_content):
    """Extract text from PDF file"""
    pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_content):
    """Extract text from DOCX file"""
    doc = docx.Document(BytesIO(file_content))
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text_from_txt(file_content):
    """Extract text from TXT file"""
    return file_content.decode('utf-8')

def extract_resume_data(file_content, file_type):
    """Extract data from resume"""
    if file_type == "application/pdf":
        text = extract_text_from_pdf(file_content)
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = extract_text_from_docx(file_content)
    elif file_type == "text/plain":
        text = extract_text_from_txt(file_content)
    else:
        st.error(f"Unsupported file type: {file_type}")
        return None
    
    # Use Together AI to extract structured data from resume
    api_key = os.getenv("API_KEY")
    try:
        client = Together(api_key=api_key)
        
        prompt = f"""
        Extract structured information from this resume:

        {text[:4000]}  # Limiting text length for API

        Return the following information in JSON format:
        1. skills (as a list of strings)
        2. experience (as a list of objects with title, company, dates, and description)
        3. education (as a list of objects with degree, institution, and dates)

        Format your response ONLY as a valid JSON object containing these three keys, with no additional text.
        """
        
        with st.spinner("Extracting resume data with AI... This may take a moment"):
            response = client.chat.completions.create(
                model="Qwen/Qwen3-235B-A22B-fp8-tput",
                messages=[
                    {"role": "system", "content": "You are a resume parsing expert. Your task is to extract structured information from resumes accurately."},
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse the JSON response
            content = response.choices[0].message.content
            
            # Find JSON in the response by looking for the first '{' and the last '}'
            json_start = content.find('{')
            json_end = content.rfind('}')
            if json_start >= 0 and json_end >= 0:
                json_content = content[json_start:json_end+1]
                try:
                    resume_data = json.loads(json_content)
                    st.success("Resume successfully parsed!")
                    return resume_data
                except json.JSONDecodeError:
                    st.error("Error parsing AI response. Please enter resume data manually.")
            else:
                st.error("Could not find valid JSON in AI response. Please enter resume data manually.")
                
    except Exception as e:
        st.error(f"Error extracting resume data: {e}")
    
    return None

def match_jobs_with_ai(resume_data: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Match resume data with jobs using Together AI
    """
    api_key = "4d431bb4072e6a0ec459e1dca45f54c00f784f3551bae8f7c2264b5f8c7fee2f"

    # Check if resume data is empty
    if not resume_data.get("skills") and not resume_data.get("experience"):
        st.warning("Please add some skills or experience to your resume first")
        return []

    try:
        client = Together(api_key=api_key)
        
        # Create a prompt that includes the resume data and preferences
        skills_str = ", ".join(resume_data.get("skills", []))
        experience_str = "\n".join([
            f"- {exp['title']} at {exp['company']} ({exp['dates']}): {exp['description']}"
            for exp in resume_data.get("experience", [])
        ])
        education_str = "\n".join([
            f"- {edu['degree']} from {edu['institution']} ({edu['dates']})"
            for edu in resume_data.get("education", [])
        ])
        
        prompt = f"""
        Based on the following resume information and job preferences, generate 5 relevant job matches.
        
        Resume Information:
        Skills: {skills_str}
        
        Experience:
        {experience_str}
        
        Education:
        {education_str}
        
        Job Preferences:
        - Location Type: {preferences.get('location_type', 'Any')}
        - Experience Level: {preferences.get('experience_level', 'Any')}
        - Job Type: {preferences.get('job_type', 'Full-time')}
        - Industry: {preferences.get('industry', 'Any')}
        
        For each job match, provide:
        1. Job title
        2. Company name
        3. Location (including whether it's remote, hybrid, or onsite)
        4. Salary range
        5. Required skills (ordered by importance)
        6. Job description
        7. A matching score from 0-100 based on how well the resume matches the job
        8. Application URL
        
        Format your response as a JSON array of job objects. Do not include any extra text outside the JSON.
        """
        
        with st.spinner("Generating job matches with AI... This may take a moment"):
            response = client.chat.completions.create(
                model="Qwen/Qwen3-235B-A22B-fp8-tput",
                messages=[
                    {"role": "system", "content": "You are a job matching expert. Your task is to generate highly relevant job matches based on resume data and preferences."},
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse the JSON response
            content = response.choices[0].message.content
            
            # Find JSON in the response by looking for the first '{' and the last '}'
            json_start = content.find('{')
            json_end = content.rfind('}')
            if json_start >= 0 and json_end >= 0:
                json_content = content[json_start:json_end+1]
                try:
                    jobs_data = json.loads(json_content)
                except json.JSONDecodeError:
                    st.error("Error parsing AI response. Using mock data instead.")
                    return generate_mock_job_matches(resume_data, preferences)
            else:
                # Try to find a JSON array
                json_start = content.find('[')
                json_end = content.rfind(']')
                if json_start >= 0 and json_end >= 0:
                    json_content = content[json_start:json_end+1]
                    try:
                        jobs_data = json.loads(json_content)
                    except json.JSONDecodeError:
                        st.error("Error parsing AI response. Using mock data instead.")
                        return generate_mock_job_matches(resume_data, preferences)
                else:
                    st.error("Could not find valid JSON in AI response. Using mock data instead.")
                    return generate_mock_job_matches(resume_data, preferences)
            
            # Ensure we have a list of jobs
            if isinstance(jobs_data, dict) and "jobs" in jobs_data:
                jobs = jobs_data["jobs"]
            elif isinstance(jobs_data, list):
                jobs = jobs_data
            else:
                jobs = []
            
            if not jobs:
                st.warning("No job matches found. Using mock data instead.")
                return generate_mock_job_matches(resume_data, preferences)
                
            return jobs

    except Exception as e:
        st.error(f"Error matching jobs with AI: {e}")
        return generate_mock_job_matches(resume_data, preferences)

    
def generate_mock_job_matches(resume_data: Dict[str, Any], preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate mock job match data"""
    try:
        from faker import Faker
        fake = Faker()
    except ImportError:
        st.error("Faker package not installed. Please install with 'pip install faker'")
        # Create a simple fake data generator as fallback
        class SimpleFake:
            def company(self):
                companies = ["TechCorp", "DataSystems", "InnovateTech", "CodeWizards", "CloudNine"]
                return random.choice(companies)
            
            def paragraph(self, nb_sentences=5):
                sentences = [
                    "Looking for a talented professional to join our team.",
                    "Must have experience with modern development tools.",
                    "Great opportunity for career growth.",
                    "Competitive salary and benefits package.",
                    "Exciting projects with cutting-edge technology.",
                    "Work with a diverse team of professionals.",
                    "Flexible work arrangements available."
                ]
                return " ".join(random.sample(sentences, min(nb_sentences, len(sentences))))
        
        fake = SimpleFake()
    
    # Use resume skills to make matches somewhat relevant
    skills = resume_data.get("skills", ["Python", "Data Analysis", "Project Management"])
    
    # Job titles related to common skills
    job_titles = [
        "Senior Software Engineer", 
        "Data Scientist",
        "Product Manager",
        "Full Stack Developer",
        "UX/UI Designer",
        "DevOps Engineer",
        "AI Researcher",
        "Machine Learning Engineer"
    ]
    
    # Location preferences
    location_type = preferences.get("location_type", "Any")
    if location_type == "Remote":
        locations = ["Remote", "Remote", "Remote", "Remote (US)", "Remote (Global)"]
    elif location_type == "Hybrid":
        locations = ["Hybrid - New York, NY", "Hybrid - San Francisco, CA", "Hybrid - Austin, TX", 
                   "Hybrid - Seattle, WA", "Hybrid - Boston, MA"]
    elif location_type == "Onsite":
        locations = ["New York, NY", "San Francisco, CA", "Austin, TX", "Seattle, WA", "Boston, MA"]
    else:
        locations = ["Remote", "Hybrid - New York, NY", "San Francisco, CA", 
                   "Remote (US)", "Hybrid - Austin, TX"]
    
    # Generate 5-8 job matches
    num_matches = random.randint(5, 8)
    job_matches = []
    
    for i in range(num_matches):
        # Select some of the resume skills plus some additional ones
        user_skills = set(skills)
        all_skills = list(user_skills) + ["Teamwork", "Communication", "Problem Solving", 
                                       "Java", "JavaScript", "React", "Node.js", "AWS",
                                       "Docker", "Kubernetes", "SQL", "NoSQL", "Git",
                                       "CI/CD", "Agile", "Scrum"]
        
        # Randomly select 5-10 required skills, prioritizing those from the resume
        num_required = random.randint(5, 10)
        resume_skills_count = min(len(user_skills), num_required - 2)
        required_skills = list(random.sample(list(user_skills), resume_skills_count)) if user_skills else []
        
        # Add some additional skills
        remaining_skills = [s for s in all_skills if s not in required_skills]
        required_skills.extend(random.sample(remaining_skills, num_required - len(required_skills)))
        
        # Calculate match score based on how many of the user's skills match
        if skills and required_skills:
            skill_match_pct = len(set(skills).intersection(set(required_skills))) / len(required_skills)
            match_score = int(70 + skill_match_pct * 30) 
        else:
            match_score = random.randint(70, 95)
        
        match_score = min(100, max(70, match_score + random.randint(-5, 5)))
        
        title = random.choice(job_titles)
        if "Senior" in title or "Lead" in title:
            salary_range = f"${random.randint(120, 180)}K - ${random.randint(181, 220)}K"
        else:
            salary_range = f"${random.randint(80, 110)}K - ${random.randint(111, 150)}K"
        
        job_match = {
            "title": title,
            "company": fake.company(),
            "location": random.choice(locations),
            "salary": salary_range,
            "required_skills": required_skills,
            "description": fake.paragraph(nb_sentences=random.randint(4, 7)),
            "match_score": match_score,
            "apply_url": f"https://example.com/jobs/{i+1}"
        }
        
        job_matches.append(job_match)
    
    job_matches.sort(key=lambda x: x["match_score"], reverse=True)
    return job_matches

def main():
    st.set_page_config(page_title="AI Job Matcher", page_icon="💼", layout="wide")
    
    st.title("AI Job Matcher")
    st.write("Upload your resume or enter details manually, and get AI-powered job recommendations")
    
    if "resume_data" not in st.session_state:
        st.session_state.resume_data = {
            "skills": [],
            "experience": [],
            "education": []
        }
    
    if "preferences" not in st.session_state:
        st.session_state.preferences = {
            "location_type": "Any",
            "experience_level": "Any",
            "job_type": "Full-time",
            "industry": "Any"
        }
    
    if "jobs" not in st.session_state:
        st.session_state.jobs = None
    
    if "resume_uploaded" not in st.session_state:
        st.session_state.resume_uploaded = False
    
    tab1, tab2, tab3 = st.tabs(["Resume", "Job Preferences", "Job Matches"])
    
    with tab1:
        st.header("Resume Information")
        
        st.subheader("Upload Resume")
        uploaded_file = st.file_uploader("Upload your resume (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])
        
        if uploaded_file is not None and not st.session_state.resume_uploaded:
            file_content = uploaded_file.getvalue()
            file_type = uploaded_file.type
            
            resume_data = extract_resume_data(file_content, file_type)
            
            if resume_data:
                st.session_state.resume_data = resume_data
                st.session_state.resume_uploaded = True
        
        st.divider()
        st.subheader("Or Enter Resume Details Manually")
        
        st.subheader("Skills")
        skills_input = st.text_area(
            "Enter your skills (one per line)",
            value="\n".join(st.session_state.resume_data.get("skills", [])),
            height=100,
            help="Enter technical and soft skills relevant to your career"
        )
        
        if skills_input:
            st.session_state.resume_data["skills"] = [skill.strip() for skill in skills_input.split("\n") if skill.strip()]
        
        st.subheader("Experience")
        
        with st.expander("Add Experience"):
            exp_title = st.text_input("Job Title", key="exp_title")
            exp_company = st.text_input("Company", key="exp_company")
            exp_dates = st.text_input("Dates (e.g., Jan 2020 - Present)", key="exp_dates")
            exp_desc = st.text_area("Description", key="exp_desc")
            
            if st.button("Add Experience"):
                if exp_title and exp_company and exp_dates:
                    st.session_state.resume_data["experience"].append({
                        "title": exp_title,
                        "company": exp_company,
                        "dates": exp_dates,
                        "description": exp_desc
                    })
                    st.success("Experience added!")
                else:
                    st.error("Please fill in all required fields")
        
        if st.session_state.resume_data["experience"]:
            st.write("Current Experience:")
            for i, exp in enumerate(st.session_state.resume_data["experience"]):
                st.markdown(f"**{exp['title']} at {exp['company']}** ({exp['dates']})")
                st.write(exp['description'])
                if st.button(f"Remove", key=f"remove_exp_{i}"):
                    st.session_state.resume_data["experience"].pop(i)
                    st.experimental_rerun()
                st.divider()
        
        st.subheader("Education")
        with st.expander("Add Education"):
            edu_degree = st.text_input("Degree", key="edu_degree")
            edu_institution = st.text_input("Institution", key="edu_institution")
            edu_dates = st.text_input("Dates (e.g., 2016 - 2020)", key="edu_dates")
            
            if st.button("Add Education"):
                if edu_degree and edu_institution and edu_dates:
                    st.session_state.resume_data["education"].append({
                        "degree": edu_degree,
                        "institution": edu_institution,
                        "dates": edu_dates
                    })
                    st.success("Education added!")
                else:
                    st.error("Please fill in all required fields")
        
        if st.session_state.resume_data["education"]:
            st.write("Current Education:")
            for i, edu in enumerate(st.session_state.resume_data["education"]):
                st.markdown(f"**{edu['degree']}** from {edu['institution']} ({edu['dates']})")
                if st.button(f"Remove", key=f"remove_edu_{i}"):
                    st.session_state.resume_data["education"].pop(i)
                    st.experimental_rerun()
                st.divider()
        
        if st.button("Reset All Resume Data"):
            st.session_state.resume_data = {
                "skills": [],
                "experience": [],
                "education": []
            }
            st.session_state.resume_uploaded = False
            st.success("Resume data reset!")
            st.experimental_rerun()
    
    with tab2:
        st.header("Job Preferences")
        
        location_options = ["Any", "Remote", "Hybrid", "Onsite"]
        experience_options = ["Any", "Entry Level", "Mid Level", "Senior", "Executive"]
        job_type_options = ["Any", "Full-time", "Part-time", "Contract", "Internship"]
        industry_options = [
            "Any", "Technology", "Finance", "Healthcare", "Education", 
            "E-commerce", "Manufacturing", "Media", "Consulting"
        ]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.preferences["location_type"] = st.selectbox(
                "Location Type",
                options=location_options,
                index=location_options.index(st.session_state.preferences["location_type"])
            )
            
            st.session_state.preferences["experience_level"] = st.selectbox(
                "Experience Level",
                options=experience_options,
                index=experience_options.index(st.session_state.preferences["experience_level"])
            )
        
        with col2:
            st.session_state.preferences["job_type"] = st.selectbox(
                "Job Type",
                options=job_type_options,
                index=job_type_options.index(st.session_state.preferences["job_type"])
            )
            
            st.session_state.preferences["industry"] = st.selectbox(
                "Industry",
                options=industry_options,
                index=industry_options.index(st.session_state.preferences["industry"])
            )
        
        st.divider()
        additional_notes = st.text_area("Additional Preferences (optional)", height=100)
        if additional_notes:
            st.session_state.preferences["notes"] = additional_notes
    
    with tab3:
        st.header("Job Matches")
        
        if not st.session_state.resume_data["skills"] and not st.session_state.resume_data["experience"]:
            st.warning("Please add your skills and experience in the Resume tab before generating job matches")
        else:
            if st.button("Generate Job Matches") or st.session_state.jobs:
                if not st.session_state.jobs:
                    jobs = match_jobs_with_ai(st.session_state.resume_data, st.session_state.preferences)
                    st.session_state.jobs = jobs
                
                if st.session_state.jobs:
                    for job in st.session_state.jobs:
                        with st.container():
                            col1, col2 = st.columns([3, 1])
                            
                            job_title = job.get('title', job.get('job_title', 'Unknown Position'))
                            company = job.get('company', job.get('company_name', 'Unknown Company'))
                            location = job.get('location', 'Location not specified')
                            
                            with col1:
                                st.markdown(f"### {job_title}")
                                st.markdown(f"**{company}** | {location}")
                            
                            with col2:
                                match_score = job.get('match_score', job.get('score', 0))
                                if isinstance(match_score, str):
                                    try:
                                        match_score = int(match_score.rstrip('%'))
                                    except ValueError:
                                        match_score = 0
                                        
                                st.markdown(f"**Match Score: {match_score}%**")
                                st.progress(min(match_score/100, 1.0))
                            
                            salary = job.get('salary', job.get('salary_range', 'Not specified'))
                            st.markdown(f"**Salary Range:** {salary}")
                            
                            skills = job.get('required_skills', job.get('skills', []))
                            if skills:
                                st.markdown("#### Required Skills")
                                if isinstance(skills, list):
                                    st.markdown(", ".join(skills))
                                else:
                                    st.markdown(str(skills))
                            
                            description = job.get('description', job.get('job_description', 'No description available'))
                            st.markdown("#### Job Description")
                            st.write(description)
                            
                            apply_url = job.get('apply_url', job.get('url', 'https://example.com/jobs'))
                            st.markdown(f"[Apply Now]({apply_url})")
                            st.divider()
                else:
                    st.error("No job matches found. Please try adjusting your resume or preferences.")
            
            if st.session_state.jobs and st.button("Reset Job Matches"):
                st.session_state.jobs = None
                st.experimental_rerun()

if __name__ == "__main__":
    main()