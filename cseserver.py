import asyncio
import json
from openai import OpenAI
import spacy
import logging
import os
import re
from nltk.corpus import wordnet as wn
import nltk
from spacy.cli import download  # Correct import
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from celery.result import AsyncResult
from celery import shared_task
from celery_app import celery_app  # Import the initialized Celery instance
from tasks import analyze_text_async  # Import the task


# Configure logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log"),  # Log to a file named server.log
        logging.StreamHandler()  # Also print to console
    ]
)

logger = logging.getLogger(__name__)  # Create a logger instance


client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize FastAPI app
app = FastAPI()
                  

# Load SpaCy model
try:
    nlp = spacy.load('en_core_web_md')
except OSError:
    download('en_core_web_md')
    nlp = spacy.load('en_core_web_md')

HARDCODED_TOPICS = [
    # Health and Medicine
    "vaccines", "COVID-19", "autism", "5G", "pharmaceuticals", "mental health", "cancer", "GMOs", "alternative medicine",
    # Science and Technology
    "climate change", "evolution", "artificial intelligence", "space exploration", "renewable energy",
    # Politics and Elections
    "election fraud", "voter ID laws", "immigration", "political conspiracies", "Deep State", "QAnon", 
    # Conspiracies and General Misinformation
    "chemtrails", "flat Earth", "9/11 conspiracies", "moon landing hoax", "New World Order",
    # Social Issues
    "racism", "xenophobia", "islamaphobia", "BLM", "Antifa",
    # Economics
    "inflation", "cryptocurrency", "wealth inequality", "globalization",
    # Environment
    "deforestation", "pollution", "carbon emissions", "wildlife conservation", "global warming"
    ]

def is_valid_sentence(sentence):
    """Check if a sentence is valid based on length and content."""
    if len(sentence.split()) < 5 or re.search(r'https?://', sentence):
        return False
    if any(nav_word in sentence.lower() for nav_word in ['menu', 'navigation', 'search']):
        return False
    return True

def get_synonyms(word):
    """Get synonyms for a word using WordNet."""
    synonyms = set()
    for syn in wn.synsets(word):
        for lemma in syn.lemmas():
            synonyms.add(lemma.name().lower())
    return synonyms

def is_relevant_sentence(sentence, topics, min_similarity=0.75):
    """Check if a sentence matches topics or has semantic similarity."""
    doc = nlp(sentence)
    # Filter out non-vectorized tokens and stop words
    filtered_tokens = [token for token in doc if not token.is_stop and (token.has_vector or token.ent_type_ != '')]
    
    # If no relevant tokens are found, skip similarity calculation
    if not filtered_tokens:
        return False
    for topic in topics:
        if any(word in sentence.lower() for word in get_synonyms(topic)):
            return True
        # Calculate semantic similarity
        topic_doc = nlp(topic)
        if doc.similarity(topic_doc) > min_similarity:
            return True
            
    return False

def analyze_chunk(chunk):
    """Analyze a chunk of relevant sentences using ChatGPT."""
    messages = [
        {"role": "system", "content": "Analyze the following text for misinformation."},
        {"role": "user", "content": chunk}
    ]
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=1000,
            temperature=0.2
        )
        logger.info("chunk of relevent sentences summarized")
        logger.info(f"chunk analysis:{(response.choices[0].message.content.strip())[0:100]}")
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error in GPT-3 request: {str(e)}")
        return "Error in GPT analysis."

def unify_analysis(analyses):
    """Unify multiple analyses into a single cohesive summary."""
    combined = ' '.join(analyses)
    messages = [
        {"role": "system", "content": "Unify and remove redundant information from the following text."},
        {"role": "user", "content": combined}
    ]
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=1000,
            temperature=0.2
        )
        logger.info("8. unify all chunk summaries")
        logger.info(f"unified analysis:{(response.choices[0].message.content.strip())[0:100]}")
        return response.choices[0].message.content.strip()
    except Exception as e:
        app.logger.error(f"Error in GPT-3 unification request: {str(e)}")
        return "Error in unifying the analysis."

@celery_app.task  # This makes it a Celery task
def analyze_large_text_batched(text, topics, token_limit=3000):
    """Incrementally analyze text in 50-sentence batches."""
    all_analyses = []  # Store the analyses
    buffer = []  # Accumulate relevant sentences for summarization
    token_count = 0  # Track the token usage of the buffer
    logger.info("Starting analysis of entire web-page")

    def estimate_token_count(text):
        """Estimate the token count for a chunk."""
        return len(text.split())

    def process_chunk():
        """Analyze the buffer and reset it."""
        nonlocal buffer, token_count
        logger.info("Sending buffer to ChatGPT")
        analysis = analyze_chunk(' '.join(buffer))
        all_analyses.append(analysis)
        buffer = []  # Reset buffer
        token_count = 0  # Reset token count

    sentence_start = 0
    sentences = text.split('. ')
    chunkiterationcounter = 0

    while sentence_start < len(sentences):
        chunkiterationcounter += 1
        chunk = sentences[sentence_start:sentence_start + 50]
        sentence_start += 50
        logger.info(f"Processing chunk {chunkiterationcounter} ending in {chunk[0:1]}")

        relevant_sentences = [
            sent for sent in chunk if is_valid_sentence(sent) and is_relevant_sentence(sent, topics)
        ]

        if not relevant_sentences:
            logger.info(f"Chunk {chunkiterationcounter}: No relevant sentences found")
            continue

        logger.info(f"Chunk {chunkiterationcounter}: Relevant sentences found")
        chunk_text = ' '.join(relevant_sentences)
        chunk_token_count = estimate_token_count(chunk_text)

        if token_count + chunk_token_count > token_limit:
            logger.info("Analyzing current buffer")
            process_chunk()

        buffer.extend(relevant_sentences)
        token_count += chunk_token_count

    if buffer:
        logger.info("Analyzing remaining buffer")
        process_chunk()

    if len(all_analyses) > 1:
        logger.info("Unifying multiple analyses")
        return unify_analysis(all_analyses)
    elif all_analyses:
        logger.info("Only one analysis result found. Skipping unification.")
        return all_analyses[0]
    else:
        return {"message": "No relevant information found."}["message"]  # Access the value of the "message" key


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection opened.")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get('type') == 'ping':
                logger.info("Received keepalive ping")
                await websocket.send_text(json.dumps({'message': 'pong'}))

            elif message.get('action') == 'analyze_text' and 'text' in message:
                logger.info("Received text for analysis")

                requestInfo = message.get('requestInfo')  # Get requestInfo // This line was modified or newly added

                # Call Celery task asynchronously
                task = analyze_text_async.delay(message['text'], HARDCODED_TOPICS)

                # Wait for the task result
                result = task.get(timeout=600)  # Blocks until result is available

                # Send the result back through WebSocket
                response = json.dumps({'result': result, 'requestInfo': requestInfo})  # Include requestInfo in the response // This line was modified or newly added
                await websocket.send_text(response)
                logger.info(f"Sent analysis result: {response}")
            else:
                await websocket.send_text(json.dumps({'error': 'Invalid request'}))

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed.")

@app.get("/task-result/{task_id}")
async def get_task_result(task_id: str):
    """Endpoint to fetch the task result using its ID."""
    task_result = AsyncResult(task_id)
    if task_result.state == 'PENDING':
        return {"status": "Processing"}
    elif task_result.state == 'SUCCESS':
        return {"status": "Completed", "result": task_result.result}
    else:
        return {"status": "Failed"}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run("cseserver:app", host="0.0.0.0", port=5000, log_level="info")

