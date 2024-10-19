from flask import Flask, jsonify, request
from openai import OpenAI
import configparser
import spacy
from flask_cors import CORS
import logging
import os
import re
from nltk.corpus import wordnet as wn
import nltk
from spacy.cli import download  # Correct import

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Configure logger if running under Gunicorn
if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

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

def text_streamer(text, chunk_size=50):
    """Yield chunks of 50 sentences from the full text."""
    sentences = text.split('. ')
    for i in range(0, len(sentences), chunk_size):
        yield '. '.join(sentences[i:i + chunk_size])

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
        return response.choices[0].message.content.strip()
    except Exception as e:
        app.logger.error(f"Error in GPT-3 request: {str(e)}")
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
        return response.choices[0].message.content.strip()
    except Exception as e:
        app.logger.error(f"Error in GPT-3 unification request: {str(e)}")
        return "Error in unifying the analysis."

def analyze_large_text_batched(text, topics, token_limit=3000):
    """Batch chunks of relevant sentences until the token limit is reached."""
    all_analyses = []  # Store the analyses
    batch = []  # Accumulate relevant sentences across chunks
    token_count = 0  # Track token usage

    def estimate_token_count(text):
        """Estimate the token count for a chunk."""
        return len(text.split())

    for chunk_number, chunk in enumerate(text_streamer(text)):
        # Collect relevant sentences from the current chunk
        relevant_sentences = [
            sent for sent in chunk.split('. ') if is_valid_sentence(sent) and is_relevant_sentence(sent, topics)
        ]

        if not relevant_sentences:
            continue  # Skip empty chunks with no relevant sentences

        # Calculate the token size for the entire chunk of relevant sentences
        chunk_text = ' '.join(relevant_sentences)
        chunk_token_count = estimate_token_count(chunk_text)

        # If adding this chunk exceeds the token limit, send the current batch
        if token_count + chunk_token_count > token_limit:
            analysis = analyze_chunk(' '.join(batch))  # Send current batch
            all_analyses.append(analysis)  # Store the result
            batch = []  # Reset the batch
            token_count = 0  # Reset the token count

        # Add the chunk to the batch and update the token count
        batch.append(chunk_text)
        token_count += chunk_token_count

    # Analyze any remaining sentences in the final batch
    if batch:
        analysis = analyze_chunk(' '.join(batch))
        all_analyses.append(analysis)

    # Unify all analyses
    return unify_analysis(all_analyses) if all_analyses else {"message": "No relevant information found."}


@app.route('/analyze', methods=['POST'])
def analyze():
    """Handle POST requests for analyzing text."""
    data = request.json
    text = data.get('text')

    if text:
        analysis_results = analyze_large_text_batched(text, HARDCODED_TOPICS)
        return jsonify({'status': 'success', 'analysis_results': analysis_results})
    else:
        app.logger.error("No text provided.")
        return jsonify({'error': 'No text provided'}), 400

if __name__ == '__main__':
    app.run(debug=True)
