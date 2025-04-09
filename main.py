#!/usr/bin/env python3
"""Main entry point for redaction pipeline and Flask server."""

import argparse
import subprocess
import time
import os
from tqdm import tqdm
from excel_reader import OllamaClient, ExcelReader, \
get_latest_processed_note_id,\
    process_note,send_to_flask



def run_flask_subprocess():
    """Start Flask app in a subprocess."""
    return subprocess.Popen(
        ["python", os.path.join("flask_app", "app.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )



def run_redaction_pipeline(file_path: str):
    """Process the Excel file and send redacted data to the Flask server."""
    client = OllamaClient(model="llama3.3")
    reader = ExcelReader(file_path)
    latest_note_id = get_latest_processed_note_id()
    all_rows = list(reader.read_row_as_dict())
    for idx, row in enumerate(tqdm(all_rows, desc="Processing Notes")):
        note_id = idx + 1
        if note_id <= latest_note_id:
            continue
        discharge_text = row.get("Discharge Summary", "")
        if not discharge_text.strip():
            continue

        print(f"\n🔍 Note {note_id}: splitting into sentences...")
        redacted_sentences = process_note(note_id, discharge_text, client, True, 5)
        send_to_flask(note_id, redacted_sentences)

def main():
    """Main loop logic."""
    parser = argparse.ArgumentParser(description="Run LLM redaction pipeline.")
    parser.add_argument(
        "-f", "--filepath", type=str, required=True,
        help="Path to Excel file containing discharge summaries"
    )
    args = parser.parse_args()

    flask_proc = run_flask_subprocess()
    print(f"Started Flask server (PID: {flask_proc.pid})")
    time.sleep(1)  # give Flask time to start

    try:
        run_redaction_pipeline(args.filepath)
        print("Redaction pipeline complete.")
        print("Flask server is still running. Press Ctrl+C to quit when ready.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupted by user.")


if __name__ == "__main__":
    main()
