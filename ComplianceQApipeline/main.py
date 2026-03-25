"""
For compliance QA pipeline, we need to extract insights from videos.
This module provides services to interact with 
Azure Video Indexer API to index videos and retrieve insights.
"""

import uuid
import json
import logging
from pprint import pprint

from dotenv import load_dotenv
load_dotenv(override=True)

from backend.src.graph.workflow import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"  
)
logger = logging.getLogger("Advert_Analysis_Gaurd")

def run_cli_simulation():
    """
    Simulate the video compliance and audting
    """

    #generate the session id for the workflow run
    session_id = str(uuid.uuid4())
    logger.info(f"Starting the compliance QA workflow simulation with session ID: {session_id}")

    #define the initial state
    initial_inputs = {
        "video_url": "https://youtu.be/dT7S75eYhcQ",
        "video_id": f"vid_{session_id[:8]}",
        "compliance_results": [],
        "errors": []
    }

    print("-----Initial Input for the Workflow-----")
    print(f"Input payload: {json.dumps(initial_inputs, indent=2)}")

    try:
        final_state = app.invoke(initial_inputs)
        print("-----Final Output from the Workflow-----")

        print("\n Compliance Audit report = ")
        print(f"Video ID: {final_state.get('video_id')}")
        print(f"Status: {final_state.get('final_status')}")
        print("\n [Violation Detected]")

        results = final_state.get("compliance_results", [])
        if results:
            for issue in results:
                print(f"- [{issue.get('severity')}] [{issue.get('category')}] {issue.get('description')}")
        else:
            print("No violations detected. The video is compliant with the policies.")
        print("\n[Final Summary]")
        print(final_state.get("final_report"))

    except Exception as e:
        logger.error(f"Error during workflow execution: {str(e)}")
        raise e
    
if __name__ == "__main__":
    run_cli_simulation()