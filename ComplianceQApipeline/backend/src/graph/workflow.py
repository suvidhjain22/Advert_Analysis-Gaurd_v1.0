'''
This module defines the DAG: directed acyclic graph this orchestrates
the video compliance audit process, it basically connects 
the nodes using the StateGraph using LangGraph.

START > index_video_node > audit_content_node > END
'''

from langgraph.graph import StateGraph, END
from backend.src.graph.state import VideoAuditState

from backend.src.graph.nodes import (
    index_video_node,
    audio_content_node
)

def create_graph():
    '''
    Constructs and combines the langgraph workflow
    Returns:
    Compile graph: runnable graph object for execution.
    '''
    #initialize the graph with state schema
    workflow = StateGraph(VideoAuditState)
    #add the nodes
    workflow.add_node("indexer", index_video_node)
    workflow.add_node("auditor", audio_content_node)
    #define the entry points: indexer_node
    workflow.set_entry_point("indexer")
    #define the edges
    workflow.add_edge("indexer", "auditor")
    #Once the audit is  completed, the workflow ends
    workflow.add_edge("auditor", END)
    #compile the graph
    app = workflow.compile()
    return app


#Expose the runnable app
app = create_graph()