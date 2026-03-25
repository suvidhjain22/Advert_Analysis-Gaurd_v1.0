import json
import os
import logging
import re
from typing import Dict, List, Any

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

#import state schema
from backend.src.graph.state import VideoAuditState, ComplianceIssue

#import service
from backend.src.services.video_indexer import VideoIndexerService

#Logger
logger = logging.getLogger("brand-gaurdian")
logging.basicConfig(level=logging.INFO)

#Node 1 Indexer
#Function responsible to convert video to text.
def index_video_node(state:VideoAuditState) -> Dict[str,Any]:
    '''
    Download the video from YT url
    uploads to the azure vieo indexer
    extracts the insights.
    '''
    video_url = state.get("video_url")
    video_id_input = state.get("video_id", "video_demo")

    logger.info(f"---[Node:Indexer] Processing : {video_url}")

    local_filename = "temp_audit_video.mp4"

    try:
        vi_service = VideoIndexerService()
        #download: yt-dlp
        if "youtube.com" in video_url or "youtu.be" in video_url:
            local_path = vi_service.download_youtube_video(video_url, output_path=local_filename)
        else:
            raise Exception("Please provide a valid youtube url for this.")
        
        #upload
        azure_video_id = vi_service.upload_video(local_path, video_name=video_id_input)
        logger.info(f"Upload success. Azure ID: {azure_video_id}")
        #cleanup
        if os.path.exists(local_path):
            os.remove(local_path)
        #wait
        raw_insights = vi_service.wait_for_processing(azure_video_id)
        #extract
        clean_data = vi_service.extract_data(raw_insights)
        logger.info("---[Node: Indexer] Extraction Complete---")
        return clean_data
    
    except Exception as e:
        logger.error(f"Video Indexer Failed: {e}")
        return {
            "errors": [str(e)],
            "final_status": "Fail",
            "transcript": "",
            "ocr_text": []
        }


#Node 2 : Compliance Auditing
#This the brain of whole process, this would contain the OCR text which would judge the content.
def audio_content_node(state:VideoAuditState) -> Dict[str, Any]:
    '''
    Performs RAG to audit the content - brand video
    '''
    logger.info("---[Node: Auditor] quering the knowledge base and LLM")
    transcript = state.get("transcript", "")
    if not transcript:
        logger.warning("No transcript available, skipping auditing")
        return{
            "final_status": "Fail",
            "final_report": "Audit Skipped because video processing failed(No Transcript)"
        }

    #Intialize the client
    llm = AzureChatOpenAI(
        azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature = 0
    )

    embeddings = AzureOpenAIEmbeddings(
        azure_deployment = "text-embedding-3-small",
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    )

    vector_store=AzureSearch(
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key = os.getenv("AZURE_SEARCH_API_KEY"),
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME"),
        embedding_function = embeddings.embed_query
    )

    #RAG retrieval part
    ocr_text = state.get("ocr_text", [])
    query_text = f"{transcript} {''.join(ocr_text)}"
    docs = vector_store.similarity_search(query_text, k=3)
    retrived_rules =  "\n\n".join([doc.page_content for doc in docs])
    #
    system_prompt= f"""
    You are a senior brand compliance auditor.
    OFFICIAL REULATORY OFFICER
    {retrived_rules}
    INSTRUCTIONS:
    1. Analyze the transcript and oct text below.
    2. identify Any voilations of the rules.
    3. Return strictly JSON in the following format.
        {{
    "compliance_results": [
        {{
        "category": "Claim Validation",
        "severity": "CRITICAL",
        "description": "Explanation of the violation..."
        }}
    ],
    "status": "FAIL",
    "final_report": "Summary of findings..."
    }}

    If no violations are found set the "status" to "pass" or "compliance_results" to []
    """

    user_message = f"""
    VIDEO_METADATA: {state.get('video_metadata', {})}
    TRANSCRIPT: {transcript}
    ON_SCREEN TEXT(OCR): {ocr_text}
    """

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])
        content = response.content
        if "```" in content:
            content = re.search(r"```(?:json)?(.?)```", content, re.DOTALL).group(1)
        audit_data = json.loads(content.strip())
        return{
            "compliance_results": audit_data.get("compliance-results", []),
            "final_status": audit_data.get("status", "FAIL"),
            "final_report": audit_data.get("final_report", "No report generated")
        }

    except Exception as e:
        logger.error(f"System Error in the auditer node: {str(e)}")
        #logging the raw response
        logger.error(f"Raw LLM response : {response.content if 'response' in locals() else 'None'}")
        return{
            "errors": [str(e)],
            "final_status": "FAIL" 
        }