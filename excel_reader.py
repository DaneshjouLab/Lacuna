"""Client module to redact sentences using Ollama and send to Flask."""

import os
import json
import urllib.request
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Union
from collections import defaultdict
import pandas as pd
import spacy
from spacy.cli import download
from tqdm import tqdm

# Constants
OLLAMA_BASE_URL = "http://localhost:11434"
CHAT_ENDPOINT = "/api/chat"
FLASK_ENDPOINT = "http://localhost:8000/receive-sentences"
EXCEL_PATH = os.environ.get("EXCEL_FILE")

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model: en_core_web_sm...")
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def split_into_sentences(text, n=3):
    """Split text into sentences and join every n sentences into one string."""
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    return [' '.join(sentences[i:i+n]) for i in range(0, len(sentences), n)]

class ExcelReader:
    """Read Excel rows as dictionaries."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = pd.read_excel(file_path)

    def read_row_as_dict(self):
        """Yield rows from Excel as dictionaries."""
        for row in self.data.to_dict(orient="records"):
            yield row


@dataclass
class Message:
    """Ollama message."""
    role: str
    content: str

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return {"role": self.role, "content": self.content}


class OllamaClient:
    """Chat API client for Ollama."""

    def __init__(self, model: str = "llama3.2:1b", base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.endpoint = f"{base_url}{CHAT_ENDPOINT}"

    def send_chat(self, messages: List[Union[dict, Message]]) -> Dict:
        """Send chat messages to Ollama and return response."""
        payload = {
            "model": self.model,
            "messages": [
                msg.to_dict() if isinstance(msg, Message) else msg for msg in messages
            ],
            "stream": False
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req) as response:
                result = response.read().decode("utf-8")
                return json.loads(result)

        except urllib.error.HTTPError as err:
            error_msg = err.read().decode()
            print("HTTP Error:", error_msg)
            if "model" in error_msg and "not found" in error_msg:
                user_input = input(f"Model '{self.model}' not found. Pull it? [y/N]: ").strip().lower()
                if user_input == "y":
                    subprocess.run(["ollama", "pull", self.model], check=True)
                    return self.send_chat(messages)
            raise


def redact_sentence(sentence: str, client: OllamaClient) -> str:
    """Send a sentence to the LLM for redaction."""
    prompt = (
    "You are a clinical de-identification assistant. "
    "Your task is to remove any identifiable information from the following sentence "
    "while preserving clinical relevance. Replace names, locations, and IDs with [REDACTED]."
    "ONLY GIVE REDACTED SENTENCE AND NO COMMENTARY"
    "THESE ARE NOT REAL CASES, AND YOU CANNOT REFUSE TO TRY REDACTING INFORMATION\n\n"
    f"Sentence: {sentence}"
)
    messages = [Message(role="user", content=prompt)]
    response = client.send_chat(messages)
    return response["message"]["content"]


def send_to_flask(note_id: int, sentences: List[Dict]):
    """Send structured redacted sentences to Flask."""
    payload = {
        "note_id": note_id,
        "sentences": sentences
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        FLASK_ENDPOINT,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            print("Flask response:", response.read().decode())
    except urllib.error.HTTPError as err:
        print("Error sending to Flask:", err.read().decode())
        raise

def ask_for_sentences_from_flask():
    """Ask the user to provide sentences from Flask."""
    req = urllib.request.Request(
        "http://localhost:8000/sentences",
        method="GET",
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            print("Flask response:", response.read().decode())
    except urllib.error.HTTPError as err:
        print("Error sending to Flask:", err.read().decode())
        raise


def get_latest_processed_note_id():
    """Return the first note_id with any incomplete sentence (missing or blank final_sentence)."""
    try:
        req = urllib.request.Request(
            "http://localhost:8000/sentences",
            method="GET",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if not data:
                return 0
            notes = defaultdict(list)
            for s in data:
                notes[s["note_id"]].append(s)

            for note_id in sorted(notes.keys()):
                for sentence in notes[note_id]:
                    final = sentence.get("llm_sentence")
                    if final is None or final.strip() == "":
                        return note_id
            return max(notes.keys())-1
    except Exception as e:
        print("Error fetching previous sentences:", e)
        return 0


# TOOD: modify this to include the ability to or not split the features
def process_note(note_id: int,
                 discharge_text: str,
                 client: OllamaClient,
                 split_features: bool=True,
                 sentence_split:int=3) -> List[Dict]:
    """Redact and prepare a note’s sentences for upload."""
    if split_features:
        sentences = split_into_sentences(discharge_text,sentence_split)
    else:
        sentences = [discharge_text]
    results = []

    for idx, sentence in enumerate(tqdm(sentences, desc=f"Note {note_id}: Sentences", leave=False)):
        redacted = redact_sentence(sentence, client)
        results.append({
            "index": idx,
            "original": sentence,
            "llm": redacted,
            "final": None
        })

    return results
