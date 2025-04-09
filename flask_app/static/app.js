const sentenceContainer = document.getElementById("editable-sentence");
const originalContainer = document.getElementById("original-sentence");
const stateDiv = document.getElementById("state");

const undoStack = [];

let currentSentenceId = null;

function renderEditableSentence(text) {
  sentenceContainer.innerHTML = "";
  undoStack.length = 0; // Clear undo stack

  const words = text.split(" ");
  words.forEach((word, i) => {
    const span = document.createElement("span");
    span.textContent = word;
    span.dataset.index = i;
    span.onclick = () => redactWord(span, word);
    sentenceContainer.appendChild(span);
    sentenceContainer.appendChild(document.createTextNode(" "));
  });
}

function redactWord(span, originalWord) {
  undoStack.push({ span, original: originalWord });
  span.textContent = "[REDACT]";
  span.onclick = null;
}

function undoRedact() {
  if (undoStack.length === 0) return;
  const { span, original } = undoStack.pop();
  span.textContent = original;
  span.onclick = () => redactWord(span, original);
}

function editSentence() {
  document.getElementById("edit-box").style.display = "block";
  const current = Array.from(sentenceContainer.childNodes)
    .map(node => node.textContent)
    .join("")
    .trim();
  document.getElementById("sentence-edit").value = current;
}

function saveEdit() {
  const newText = document.getElementById("sentence-edit").value.trim();
  renderEditableSentence(newText);
  document.getElementById("edit-box").style.display = "none";
}

function markGood() {
    const finalText = Array.from(sentenceContainer.childNodes)
      .map(node => node.textContent)
      .join("")
      .trim();
  
    if (!currentSentenceId) {
      alert("No sentence loaded.");
      return;
    }
  
    fetch(`/sentence/${currentSentenceId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ final_sentence: finalText })
    })
      .then(res => {
        if (!res.ok) throw new Error("Failed to mark good");
        return res.json();
      })
      .then(() => {
        showFeedback("✅ Sentence marked as good!");
        // Optionally disable button to prevent resubmission
        document.querySelector("button[onclick='markGood()']").disabled = false;
      })
      .catch(err => {
        console.error(err);
        showFeedback("❌ Failed to update sentence.");
      });
  }
  
  

function loadNextSentence() {
    
    fetch("/next-sentence/1")
      .then(res => {
        if (!res.ok) throw new Error("No more sentences");
        return res.json();
      })
      .then(data => {
        currentSentenceId = data.id;
        stateDiv.dataset.sentenceId = data.id;
  
        originalContainer.textContent = data.original_sentence;
        const editable = data.final_sentence || data.llm_sentence || data.original_sentence;
        renderEditableSentence(editable);
  
        // Debug info
        document.getElementById("debug-id").textContent = data.id;
        document.getElementById("debug-note-id").textContent = data.note_id;
        document.getElementById("debug-index").textContent = data.index;
  
        console.log("Loaded sentence:", data);
      })
      .catch(err => {
        console.error(err);
        alert("No more sentences to review.");
      });
  }
  function useOriginal() {
    const originalText = document.getElementById("original-sentence").textContent.trim();
    renderEditableSentence(originalText);
    showFeedback("📝 Replaced with original sentence.");
  }
  
  function showFeedback(msg) {
    const el = document.getElementById("feedback-message");
    el.textContent = msg;
    el.style.display = "block";
  }
  
  function clearFeedback() {
    const el = document.getElementById("feedback-message");
    el.textContent = "";
    el.style.display = "none";
  }

window.onload = function () {
  loadNextSentence();
};
