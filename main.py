import streamlit as st
import requests
import os
import PyPDF2  # For resume text extraction
from dotenv import load_dotenv
import google.generativeai as gen_ai
from googleapiclient.discovery import build  # For Google Search API
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import json  # For handling JSON data

# Load environment variables
load_dotenv()

# API keys
SCRAPINGDOG_API_KEY = '6721203eff4aedb1b023879b'
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", 'd1c00e40ec29748b0')  # Replace with your Custom Search Engine ID

# Configure Gemini API
gen_ai.configure(api_key=GOOGLE_API_KEY)
model = gen_ai.GenerativeModel('gemini-1.5-flash')


# --- Job Scraper Section ---
def scrape_linkedin_jobs(params):
    try:
        response = requests.get('https://api.scrapingdog.com/linkedinjobs/', params=params)
        response.raise_for_status()  # Raise an error for bad responses
        return response.json()
    except requests.HTTPError as http_err:
        st.error(f"HTTP error occurred: {http_err}")  # Specific error handling
    except Exception as e:
        st.error(f"An error occurred: {e}")
    return None

def display_job_json(jobs):
    if jobs:
        st.subheader("Scraped Job Listings")
        st.write("### Job Listings (JSON Format):")
        for job in jobs:
            st.json(job)
            st.markdown("---")  # Separator between job listings
        
        # Button to download job data as JSON
        json_data = json.dumps(jobs, indent=10)  # Convert job data to JSON format
        st.download_button(
            label="Download Job Data as JSON",
            data=json_data,
            file_name='scraped_jobs.json',
            mime='application/json'
        )
    else:
        st.warning("No job data to display.")

def job_scraper():
    with st.expander("🔍 Scrape LinkedIn Jobs", expanded=True):
        st.write("Enter the job search parameters to scrape LinkedIn jobs.")
        
        field = st.text_input("Field (e.g., Python, Data Science)", "python")
        exp_level = st.selectbox("Experience Level", ["entry_level", "mid_level", "senior_level"])
        pages = st.slider("Number of Pages to Scrape", 1, 5, 1)  # Limit to 5 pages
        
        if st.button("Scrape Jobs"):
            params = {
                'api_key': SCRAPINGDOG_API_KEY,
                'field': field,
                'geoid': '104112529',  # Geo ID for Pakistan
                'page': 1,
                'exp_level': exp_level
            }
            
            # Scrape jobs and display results
            total_jobs = []
            for page in range(1, pages + 1):  # Loop through the specified number of pages
                params['page'] = page
                jobs_data = scrape_linkedin_jobs(params)
                
                if jobs_data:
                    st.success(f"Scraped page {page} with {len(jobs_data)} jobs.")
                    total_jobs.extend(jobs_data)
                else:
                    st.warning(f"No jobs found on page {page}.")
                    
            # Display jobs in JSON format
            display_job_json(total_jobs)


# --- Chatbot Section --- 
def handle_chatbot(user_prompt):
    if 'chat_session' not in st.session_state:
        st.session_state.chat_session = model.start_chat(history=[])

    st.chat_message("user").markdown(user_prompt)
    gemini_response = st.session_state.chat_session.send_message(user_prompt)
    
    with st.chat_message('assistant'):
        st.markdown(gemini_response.text)

def chatbot():
    st.subheader("💬 Chatbot")
    st.write("Ask me anything related to job proposals or general queries.")
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Display chat history
    if st.session_state.chat_history:
        st.write("### Chat History")
        for role, message in st.session_state.chat_history:
            with st.chat_message(role.lower()):
                st.markdown(f"{role}: *{message}*")
    
    user_prompt = st.chat_input('Ask Gemini:')
    if user_prompt:
        handle_chatbot(user_prompt)
        st.session_state.chat_history.append(("User", user_prompt))
        st.session_state.chat_history.append(("Gemini", st.session_state.chat_session.history[-1].parts[0]))


# --- Software House Recommendations Section ---
def google_search(query, GOOGLE_API_KEY, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    res = service.cse().list(q=query, cx=cse_id, **kwargs).execute()
    return res['items']

def handle_software_house_recommendation_google(job_role, field, location):
    search_query = f"{field} software houses for {job_role} in {location}"
    try:
        results = google_search(search_query, GOOGLE_API_KEY, GOOGLE_CSE_ID)
        st.subheader("Recommended Software Houses")
        for result in results:
            st.write(f"[{result['title']}]({result['link']})")
            st.write(result['snippet'])
            st.markdown("---")  # Separator between search results
    except Exception as e:
        st.error(f"Error fetching software house recommendations: {e}")

def handle_software_house_recommendation_gemini(job_role, field, location):
    if 'chat_session' not in st.session_state:
        st.session_state.chat_session = model.start_chat(history=[])

    # Generate prompt for software house recommendations
    user_prompt = (f"Please suggest software houses that specialize in {field} "
                   f"for {job_role} roles in {location}.") 
    
    st.chat_message("user").markdown(user_prompt)
    gemini_response = st.session_state.chat_session.send_message(user_prompt)
    
    with st.chat_message('assistant'):
        st.markdown(gemini_response.text)

def software_house_recommendations():
    st.subheader("🏢 Software House Recommendations")
    st.write("Get a list of software houses based on your job role, field, and location.")
    
    job_role = st.text_input("Job Role (e.g., Data Scientist, Backend Developer)", "Data Scientist")
    field = st.text_input("Field (e.g., AI, Web Development)", "AI")
    location = st.text_input("Location (e.g., Islamabad, Karachi)", "Karachi")
    
    # Choose between Google search and Gemini AI for recommendations
    recommendation_method = st.radio("Choose Recommendation Method", ["Google Search", "Gemini AI"])
    
    if st.button("Get Recommendations"):
        if recommendation_method == "Google Search":
            handle_software_house_recommendation_google(job_role, field, location)
        else:
            handle_software_house_recommendation_gemini(job_role, field, location)


# --- Resume Analyzer Section ---
def extract_resume_text(resume_file):
    try:
        pdf_reader = PyPDF2.PdfReader(resume_file)
        resume_text = ""
        for page in pdf_reader.pages:
            resume_text += page.extract_text() or ""
        return resume_text
    except Exception as e:
        st.error(f"Error extracting text from resume: {e}")
        return ""

def clean_proposal_text(text):
    # Remove extra symbols, whitespace, and newlines
    cleaned_text = ' '.join(text.split())
    return cleaned_text

def create_pdf(proposal_text):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Write the proposal text to the PDF
    text = c.beginText(40, height - 40)
    text.setFont("Helvetica", 12)

    # Split the proposal text into lines for better formatting
    lines = proposal_text.splitlines()
    for line in lines:
        cleaned_line = clean_proposal_text(line)  # Clean each line
        if cleaned_line:  # Only add non-empty lines
            text.textLine(cleaned_line)

    c.drawText(text)
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer

def handle_job_suggestions_and_proposal(resume_text, job_suggestion):
    if 'chat_session' not in st.session_state:
        st.session_state.chat_session = model.start_chat(history=[])

    # Generate prompt based on the resume text and job suggestion
    user_prompt = (f"Based on this resume: {resume_text[:500]}, suggest a job proposal, skill recommendations, "
                   f"and a learning roadmap for the following job: {job_suggestion} and also give the keyword to add in my job proposal for this Job description.")
    
    st.chat_message("user").markdown(user_prompt)
    gemini_response = st.session_state.chat_session.send_message(user_prompt)
    
    with st.chat_message('assistant'):
        proposal_text = gemini_response.text
        st.markdown(proposal_text)

    return proposal_text  # Return the proposal text for PDF creation

def resume_analyzer():
    st.subheader("📄 Resume Analyzer")
    st.write("Upload your resume to receive job suggestions and tailored proposals.")
    
    resume_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])
    job_suggestion = st.text_input("Desired Job Role (e.g., Data Scientist)", "Data Scientist")
    
    if st.button("Analyze Resume"):
        if resume_file is not None:
            resume_text = extract_resume_text(resume_file)
            if resume_text:
                proposal_text = handle_job_suggestions_and_proposal(resume_text, job_suggestion)
                
                # Button to download the generated proposal as a PDF
                if proposal_text:
                    pdf_buffer = create_pdf(proposal_text)
                    st.download_button(
                        label="Download Job Proposal as PDF",
                        data=pdf_buffer,
                        file_name='job_proposal.pdf',
                        mime='application/pdf'
                    )
        else:
            st.warning("Please upload a resume PDF.")

# --- Main Application ---
def main():
    st.title("Job Portal and Chatbot")
    st.write("Welcome to the Job Portal! Use the features below to find jobs, analyze your resume, and interact with the chatbot.")
    
    # Navigation bar in sidebar
    st.sidebar.title("Navigation")
    options = ["Job Scraper", "Chatbot", "Software House Recommendations", "Resume Analyzer"]
    choice = st.sidebar.selectbox("Select an Option", options)

    if choice == "Job Scraper":
        job_scraper()
    elif choice == "Chatbot":
        chatbot()
    elif choice == "Software House Recommendations":
        software_house_recommendations()
    elif choice == "Resume Analyzer":
        resume_analyzer()

if __name__ == "__main__":
    main()