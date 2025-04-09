"""Flask app for handling note de-identification and sentence-level storage."""

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy setup
db = SQLAlchemy()

# ------------------- Models -------------------
# pylint: disable=too-few-public-methods
class Note(db.Model):
    """Table storing discharge notes and metadata."""
    note_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=True)
    discharge_summary = db.Column(db.Text, nullable=True)
    clinician_1 = db.Column(db.Text, nullable=True)
    clinician_2 = db.Column(db.Text, nullable=True)
    sentences = db.relationship("Sentence", backref="note", lazy=True)

# pylint: disable=too-few-public-methods
class Sentence(db.Model):
    """Table storing per-sentence de-identification mappings."""
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('note.note_id'), nullable=False)
    sentence_index = db.Column(db.Integer, nullable=False)
    original_sentence = db.Column(db.Text, nullable=False)
    llm_sentence = db.Column(db.Text, nullable=True)
    final_sentence = db.Column(db.Text, nullable=True)

# ------------------- App Factory -------------------
def create_app():
    """Initialize the Flask app with database and routes."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///my.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # ------------------- Routes -------------------

    @app.route("/", methods=["GET"])
    def index():
        """Render the homepage with a sample sentence comparison."""
        original = "The quick brown fox jumps over the lazy dog."
        edited = "The quick brown fox leaped over the lazy dog."
        return render_template("index.html", original=original, edited=edited)

    @app.route("/receive-sentences", methods=["POST"])
    def receive_sentences():
        """Receive and store sentence-level de-identification data."""
        payload = request.get_json()
        note_id = payload.get("note_id")
        sentences = payload.get("sentences")

        if not note_id or not sentences:
            return jsonify(error="Missing 'note_id' or 'sentences'"), 400

        for entry in sentences:
            if "index" not in entry or "original" not in entry:
                return jsonify(error="Each sentence must have 'index' and 'original'"), 400

            sentence = Sentence(
                note_id=note_id,
                sentence_index=entry["index"],
                original_sentence=entry["original"],
                llm_sentence=entry.get("llm")
                # final_sentence intentionally excluded
            )
            db.session.add(sentence)

        db.session.commit()
        return jsonify(message="Sentences stored"), 200

    @app.route("/sentence/<int:sentence_id>", methods=["PATCH"])
    def update_sentence(sentence_id):
        """Update the final version of a specific sentence."""
        sentence = Sentence.query.get(sentence_id)
        if sentence is None:
            return jsonify(error="Sentence not found"), 404

        payload = request.get_json()
        final_sentence = payload.get("final_sentence")

        if final_sentence is None:
            return jsonify(error="Missing 'final_sentence'"), 400

        sentence.final_sentence = final_sentence
        db.session.commit()
        return jsonify(message="Sentence updated"), 200

    @app.route("/next-sentence/<int:user_id>", methods=["GET"])
    def get_next_sentence(user_id):
        """Return the next sentence that has not been finalized."""
        sentence = Sentence.query.filter_by(final_sentence=None).order_by(Sentence.id).first()
        if sentence is None:
            return jsonify(error="No unreviewed sentences left"), 404

        return jsonify({
            "id": sentence.id,
            "note_id": sentence.note_id,
            "index": sentence.sentence_index,
            "original_sentence": sentence.original_sentence,
            "llm_sentence": sentence.llm_sentence,
            "final_sentence": sentence.final_sentence
        }), 200

    @app.route("/sentences", methods=["GET"])
    def get_sentences():
        """Return all sentences."""
        sentences = Sentence.query.all()
        return jsonify([{
            "id": sentence.id,
            "note_id": sentence.note_id,
            "index": sentence.sentence_index,
            "original_sentence": sentence.original_sentence,
            "llm_sentence": sentence.llm_sentence,
            "final_sentence": sentence.final_sentence
        } for sentence in sentences]), 200

    # ------------------- Setup DB -------------------
    with app.app_context():
        db.create_all()

    return app

# ------------------- Entrypoint -------------------
if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000, debug=True)
