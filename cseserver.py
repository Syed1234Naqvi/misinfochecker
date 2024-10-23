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

def analyze_large_text_batched(text, topics, token_limit=3000):
    """Incrementally analyze text in 50-sentence batches."""
    all_analyses = []  # Store the analyses
    buffer = []  # Accumulate relevant sentences for summarization
    token_count = 0  # Track the token usage of the buffer
    logger.info("starting analysis of entire web-page")
    def estimate_token_count(text):
        """Estimate the token count for a chunk."""
        return len(text.split())

    def process_chunk():
        """Analyze the buffer and reset it."""
        nonlocal buffer, token_count
        # Analyze the current buffer
        logger.info("sending buffer to chat-gpt")
        analysis = analyze_chunk(' '.join(buffer))
        all_analyses.append(analysis)
        # Reset the buffer and token count
        buffer = []
        token_count = 0

    # Process the web page in 50-sentence increments
    sentence_start = 0
    sentences = text.split('. ')  # Split the full text initially
    logger.info("sucesfully split full text")
    chunkiterationcounter = 0
    while sentence_start < len(sentences):
        # Get the next 50 sentences
        chunkiterationcounter+=1
        chunk = sentences[sentence_start:sentence_start + 50]
        sentence_start += 50  # Move to the next chunk
        logger.info(f"processing chunk {chunkiterationcounter} ending in {chunk[0:1]}")
        # Collect relevant sentences from the chunk
        relevant_sentences = [
            sent for sent in chunk if is_valid_sentence(sent) and is_relevant_sentence(sent, topics)
        ]
        if not relevant_sentences:
            logger.info(f"chunk {chunkiterationcounter}: no relevant sentences found")
            continue  # Skip if no relevant sentences are found
        logger.info(f"chunk {chunkiterationcounter}: relevant sentences found")
        # Add relevant sentences to the buffer
        chunk_text = ' '.join(relevant_sentences)
        logger.info("added relevent sentences to buffer")
        chunk_token_count = estimate_token_count(chunk_text)
        logger.info(f"current chunk token value:{chunk_token_count}")

        if token_count + chunk_token_count > token_limit:
            # Process the current buffer if adding this chunk would exceed the limit
            logger.info("not enough room in buffer for next chunk, analyze current buffer")
            process_chunk()

        # Add the chunk to the buffer and update token count
        buffer.extend(relevant_sentences)
        token_count += chunk_token_count
        logger.info(f"current buffer token value:{token_count}")

    # Analyze any remaining sentences in the buffer
    if buffer:
        logger.info("clear out remaining buffer after done extracting sentences from web-page")
        analysis = analyze_chunk(' '.join(buffer))
        all_analyses.append(analysis)
    chunkiterationcounter = 0
    # Unify all analyses into a final result
    if len(all_analyses) > 1:
        logger.info("unifying multiple analyses.")
        return unify_analysis(all_analyses)
    elif all_analyses:
        logger.info("Only one analysis result found. Skipping unification.")
        return all_analyses[0]
    else:
        return {"message": "No relevant information found."}

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
                result = analyze_large_text_batched(message['text'], HARDCODED_TOPICS)
                await websocket.send_text(json.dumps({'result': result}))
            else:
                await websocket.send_text(json.dumps({'error': 'Invalid request'}))

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed.")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run("cseserver:app", host="0.0.0.0", port=5000, log_level="info")

