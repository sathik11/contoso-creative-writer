import os
import json
from typing import Dict, List
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from prompty.tracer import trace
import prompty
import prompty.azure
from openai import AzureOpenAI
from dotenv import load_dotenv
from pathlib import Path
from azure.search.documents import SearchClient
from azure.search.documents.models import (
    VectorizedQuery,
    QueryType,
    QueryCaptionType,
    QueryAnswerType,
)

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT = "text-embedding-ada-002"
AZURE_AI_SEARCH_ENDPOINT = os.getenv("AI_SEARCH_ENDPOINT")
AZURE_AI_SEARCH_INDEX = "contoso-products"


@trace
def generate_embeddings(queries: List[str]) -> str:
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )

    client = AzureOpenAI(
        azure_endpoint = "https://aoai-tuf5ibk7wt6fu.services.ai.azure.com/", 
        api_version="2024-10-21",
        azure_ad_token_provider=token_provider
    )

    embeddings = client.embeddings.create(input=queries, model="text-embedding-ada-002")
    embs = [emb.embedding for emb in embeddings.data]
    items = [{"item": queries[i], "embedding": embs[i]} for i in range(len(queries))]

    return items


@trace
def retrieve_products(items: List[Dict[str, any]], index_name: str) -> str:
    search_client = SearchClient(
        endpoint="https://srch-tuf5ibk7wt6fu.search.windows.net",
        index_name=index_name,
        credential=DefaultAzureCredential(),
    )

    products = []
    for item in items:
        vector_query = VectorizedQuery(
            vector=item["embedding"], k_nearest_neighbors=3, fields="contentVector"
        )
        results = search_client.search(
            search_text=item["item"],
            vector_queries=[vector_query],
            query_type=QueryType.SEMANTIC,
            semantic_configuration_name="default",
            query_caption=QueryCaptionType.EXTRACTIVE,
            query_answer=QueryAnswerType.EXTRACTIVE,
            top=2,
        )

        docs = [
            {
                "id": doc["id"],
                "title": doc["title"],
                "content": doc["content"],
                "url": doc["url"],
            }
            for doc in results
        ]

        # Remove duplicates
        products.extend([i for i in docs if i["id"] not in [x["id"] for x in products]])

    return products


@trace
def find_products(context: str) -> Dict[str, any]:
    # Get product queries
    queries = prompty.execute("product.prompty", inputs={"context":context})
    qs = json.loads(queries)
    # Generate embeddings
    items = generate_embeddings(qs)
    # Retrieve products
    products = retrieve_products(items, "contoso-products")
    return products


if __name__ == "__main__":
    context = "Can you use a selection of tents and backpacks as context?"
    answer = find_products(context)
    print(json.dumps(answer, indent=2))
