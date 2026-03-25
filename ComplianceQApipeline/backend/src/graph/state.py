import operator
from typing import Annotated, List, Dict, Optional, Any, TypedDict

#define schema for single compliance result.

class ComplianceIssue(TypedDict):
    category: str 
    description: str #specifc detail of violation
    severity: str #Critical/Warning
    timestamp: Optional[str]


class VideoAuditState(TypedDict):
    '''
    defines the data schmea for langgraph.
    Main container that holds all the information about audit
    right from the initial URL to final report.
    '''
    #input parameters
    video_url: str
    video_id:  str

    #ingestion and extraction
    local_file_path: Optional[str]
    video_metadata: Dict[str, Any]  #{duration: 15, resolution: 1080p}
    transcript: Optional[str]
    ocr_text: List[str]

    #analysis output
    compliance_results: Annotated[List[ComplianceIssue], operator.add]

    #final deliverable
    final_status: str
    final_report: str

    #error for API timeout and etc
    errors: Annotated[List[str], operator.add]