import os
import glob
import logging
from dotenv import load_dotenv
from openai import vector_stores
load_dotenv(override=True)

#document loaders and splitters
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

#Azure components
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

#setup logging and config
logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("indexer")

def index_docs():
    """
    Read the pdf from data directory and chunks them and upload it to azure AI search
    """

    #define the paths, we would look for the data folder
    current_directory = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(current_directory, "../../backend/data")

    #check the env variables
    logger.info("="*60)
    logger.info("Enviornment configuration check:")
    logger.info(f"AZURE_OPENAI_ENDPOINT: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    logger.info(f"AZURE_OPENAI_API_VERSION: {os.getenv('AZURE_OPENAI_API_VERSION')}")
    logger.info(f"Embedding_Deployment: {os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-small')}")
    logger.info(f"AZURE_SEARCH_ENDPOINT: {os.getenv('AZURE_SEARCH_ENDPOINT')}")
    logger.info(f"AZURE_SEARCH_INDEX_NAME: {os.getenv('AZURE_SEARCH_INDEX_NAME')}")
    logger.info("="*60)

    #validate the required variables
    required_vars=[
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_API_KEY",
        "AZURE_SEARCH_INDEX_NAME"
    ]

    missing_vars=[var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing the required variables: {missing_vars}")
        logger.error("Please check your .env file  and ensure if all the variables are set")
        return

    #Initialize the embedding model
    try:
        logger.info("Initializing the AZURE OPEN AI Embeddings....")
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-small'),
            azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key = os.getenv('AZURE_OPENAI_API_KEY'),
            openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        )

        logger.info("Embeddings model is initialize succesfully.")
    except Exception as e:
        logger.error(f"Failed to initialize the embeddings: {e}")
        logger.error(f"Please verify your azure open ai deployment")
        return

    #initialize the Azure search
    try:
        logger.info("Initializing the AZURE AI Vector search store....")
        index_name = os.getenv('AZURE_SEARCH_INDEX_NAME'),
        vector_store = AzureSearch(
            azure_search_endpoint=os.getenv('AZURE_SEARCH_ENDPOINT'),
            azure_search_key=os.getenv('AZURE_SEARCH_API_KEY'),
            index_name = index_name,
            embedding_functions = embeddings.embed_query
        )
        logger.info(f"Vector store initialized for the index: {index_name}.")
    except Exception as e:
        logger.error(f"Failed to initialize the Azure AI Search : {e}")
        logger.error("Please verify your AZURE AI SEARCH Endpoint, API Key and Index name.")
        return
        

    #Find the PDF files
    pdf_files = glob.glob(os.path.join(data_folder, "*.pdf"))
    if not pdf_files:
        logger.warning(f"No pdfs found in {data_folder}, please add the files.")
    logger.info(f"Found {len(pdf_files)} PDFs to process: {[os.path.basename(f) for f in pdf_files]}")

    all_splits = []

    #process each pdf and create chunks
    for pdf_path in pdf_files:
        try:
            logger.info(f"Loading: {os.path.basename(pdf_files)}....")
            loader = PyPDFLoader(pdf_path)
            raw_docs = loader.load()

            #Chunking
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size = 1000,
                chunk_overlap = 200
            )
            splits = text_splitter.split_documents(raw_docs)
            for split in splits:
                split.metadata["Source"] = os.path.basename(pdf_path)

            all_splits.extend(splits)
            logger.info(f"Split into {len(splits)} chunks.")
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}")

        #Upload to Azure
        if all_splits:
            logger.info(f"Uploading {len(all_splits)} chunks to Azure AI Search Index '{index_name}'")
            try:
                #Azure search accepts batches automatically.
                vector_stores.add_documents(documents = all_splits)
                logger.info("="*60)
                logger.info("Indexing completed! Knowledge base is ready.")
                logger.info(f"Total chunks indexed: {len(all_splits)}")
                logger.info("="*60)

            except Exception as e:
                logger.error(f"Failed to upload the documents to Azure AI search: {e}")
                logger.error("Please check the Azure search configuration and try again.")

        else:
            logger.warning("No documents were processed.")

    if __name__ == "__main__":
        index_docs()