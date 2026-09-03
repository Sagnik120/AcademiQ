/**
 * AcademiQ — Examination Engine & Assessment Lifecycle Controller
 */

class ExamEngine {
  constructor(examId, attemptId) {
    this.examId = examId;
    this.attemptId = attemptId;
    this.questions = [];
    this.currentIndex = 0;
    this.answers = {}; // question_id -> response (option_id, array of ids, or text)
    this.flagged = new Set();
    this.timeRemaining = 3600; // default 60 minutes (seconds)
    this.timerInterval = null;
    this.autoSaveInterval = null;
  }

  async initialize() {
    try {
      // 1. Fetch attempt or questions
      const data = await this.loadExamData();
      this.questions = data.questions || [];
      this.timeRemaining = data.duration_seconds || 3600;

      // 2. Render UI
      this.renderPalette();
      this.renderQuestion(0);
      this.startTimer();
      this.startAutoSave();

      console.log(`[ExamEngine] Loaded ${this.questions.length} questions for exam ${this.examId}`);
    } catch (err) {
      console.error('[ExamEngine] Initialization error:', err);
      showToast('Could not load assessment questions', 'error');
    }
  }

  async loadExamData() {
    try {
      if (this.attemptId && this.attemptId !== 'demo-attempt-01') {
        const res = await api.get(`/learner/attempts/${this.attemptId}`);
        return res;
      }
    } catch (e) {
      console.warn('[ExamEngine] API fetch failed, loading default exam questions');
    }

    // Default High-Quality Assessment Dataset (Demo Fallback)
    return {
      title: 'Quantum Mechanics Midterm Assessment',
      duration_seconds: 3600,
      questions: [
        {
          id: 'q1',
          order_index: 1,
          question_type: 'mcq',
          marks: 2.0,
          question_text: 'What mathematical entity represents a pure state in quantum mechanics?',
          options: [
            { id: 'opt1_1', option_text: 'A ray (unit vector) in a complex Hilbert space' },
            { id: 'opt1_2', option_text: 'A real-valued Riemannian metric tensor' },
            { id: 'opt1_3', option_text: 'A deterministic classical phase space trajectory' },
            { id: 'opt1_4', option_text: 'An irreversible thermodynamic macrostate' }
          ]
        },
        {
          id: 'q2',
          order_index: 2,
          question_type: 'msq',
          marks: 3.0,
          question_text: 'Select ALL properties that characterize quantum entanglement between two particles:',
          options: [
            { id: 'opt2_1', option_text: 'The composite state cannot be factored into product states of individual particles' },
            { id: 'opt2_2', option_text: 'Measurement outcome on one particle instantaneously correlates with the other' },
            { id: 'opt2_3', option_text: 'Permits faster-than-light transmission of arbitrary classical messages' },
            { id: 'opt2_4', option_text: 'Violates Bell\'s inequality for local hidden-variable theories' }
          ]
        },
        {
          id: 'q3',
          order_index: 3,
          question_type: 'text',
          marks: 5.0,
          question_text: 'Explain the concept of quantum superposition. How does wave function collapse occur upon measurement according to the Copenhagen interpretation?'
        },
        {
          id: 'q4',
          order_index: 4,
          question_type: 'mcq',
          marks: 2.0,
          question_text: 'Which quantum logic gate is used to generate an equal superposition state from a basis state |0⟩?',
          options: [
            { id: 'opt4_1', option_text: 'Hadamard (H) Gate' },
            { id: 'opt4_2', option_text: 'Pauli-X (NOT) Gate' },
            { id: 'opt4_3', option_text: 'Controlled-NOT (CNOT) Gate' },
            { id: 'opt4_4', option_text: 'Phase-S Gate' }
          ]
        },
        {
          id: 'q5',
          order_index: 5,
          question_type: 'text',
          marks: 5.0,
          question_text: 'Discuss why quantum decoherence is a major obstacle in physical quantum computer engineering.'
        }
      ]
    };
  }

  renderPalette() {
    const paletteGrid = document.getElementById('palette-grid');
    if (!paletteGrid) return;

    paletteGrid.innerHTML = '';
    this.questions.forEach((q, idx) => {
      const btn = document.createElement('button');
      btn.className = 'palette-btn';
      btn.id = `palette-btn-${idx}`;
      btn.textContent = idx + 1;
      btn.onclick = () => this.navigateTo(idx);
      paletteGrid.appendChild(btn);
    });

    this.updatePaletteStyles();
  }

  updatePaletteStyles() {
    this.questions.forEach((q, idx) => {
      const btn = document.getElementById(`palette-btn-${idx}`);
      if (!btn) return;

      btn.className = 'palette-btn';

      const hasAnswer = this.answers[q.id] !== undefined && this.answers[q.id] !== '' && 
        (!Array.isArray(this.answers[q.id]) || this.answers[q.id].length > 0);

      if (idx === this.currentIndex) {
        btn.classList.add('current');
      } else if (this.flagged.has(q.id)) {
        btn.classList.add('flagged');
      } else if (hasAnswer) {
        btn.classList.add('answered');
      }
    });

    // Update answered counter
    const answeredCount = Object.keys(this.answers).filter(k => {
      const val = this.answers[k];
      return val !== '' && (!Array.isArray(val) || val.length > 0);
    }).length;

    const countEl = document.getElementById('answered-stats-label');
    if (countEl) {
      countEl.textContent = `${answeredCount} of ${this.questions.length} Answered`;
    }
  }

  renderQuestion(index) {
    if (index < 0 || index >= this.questions.length) return;
    this.currentIndex = index;

    const q = this.questions[index];
    document.getElementById('q-num-label').textContent = `Question ${index + 1} of ${this.questions.length}`;
    document.getElementById('q-marks-label').textContent = `[${q.marks.toFixed(1)} Marks]`;
    document.getElementById('q-type-badge').textContent = q.question_type.toUpperCase();
    document.getElementById('q-text-body').textContent = q.question_text;

    // Render Answer Input depending on type
    const container = document.getElementById('q-answer-container');
    container.innerHTML = '';

    if (q.question_type === 'mcq') {
      const list = document.createElement('div');
      list.className = 'options-list';
      (q.options || []).forEach(opt => {
        const isSelected = this.answers[q.id] === opt.id;
        const item = document.createElement('div');
        item.className = `option-item ${isSelected ? 'selected' : ''}`;
        item.innerHTML = `
          <input type="radio" name="opt_${q.id}" class="option-radio" ${isSelected ? 'checked' : ''}>
          <span style="flex: 1; font-size: 0.95rem;">${escapeHtml(opt.option_text)}</span>
        `;
        item.onclick = () => {
          this.answers[q.id] = opt.id;
          this.renderQuestion(this.currentIndex);
        };
        list.appendChild(item);
      });
      container.appendChild(list);
    } else if (q.question_type === 'msq') {
      const list = document.createElement('div');
      list.className = 'options-list';
      const selectedArr = this.answers[q.id] || [];

      (q.options || []).forEach(opt => {
        const isSelected = selectedArr.includes(opt.id);
        const item = document.createElement('div');
        item.className = `option-item ${isSelected ? 'selected' : ''}`;
        item.innerHTML = `
          <input type="checkbox" class="option-checkbox" ${isSelected ? 'checked' : ''}>
          <span style="flex: 1; font-size: 0.95rem;">${escapeHtml(opt.option_text)}</span>
        `;
        item.onclick = () => {
          let current = this.answers[q.id] || [];
          if (current.includes(opt.id)) {
            this.answers[q.id] = current.filter(id => id !== opt.id);
          } else {
            this.answers[q.id] = [...current, opt.id];
          }
          this.renderQuestion(this.currentIndex);
        };
        list.appendChild(item);
      });
      container.appendChild(list);
    } else if (q.question_type === 'text') {
      const textarea = document.createElement('textarea');
      textarea.className = 'text-answer-editor';
      textarea.placeholder = 'Type your structured essay or detailed response here... (AI evaluated on Accuracy, Completeness, Clarity)';
      textarea.value = this.answers[q.id] || '';
      textarea.oninput = (e) => {
        this.answers[q.id] = e.target.value;
        this.updatePaletteStyles();
      };
      container.appendChild(textarea);
    }

    // Toggle Flag state button
    const flagBtn = document.getElementById('btn-flag-toggle');
    if (flagBtn) {
      const isFlagged = this.flagged.has(q.id);
      flagBtn.textContent = isFlagged ? '★ Flagged' : '☆ Flag for Review';
      flagBtn.className = isFlagged ? 'btn btn-secondary btn-sm' : 'btn btn-outline btn-sm';
    }

    // Prev / Next button state
    document.getElementById('btn-prev').disabled = (index === 0);
    const nextBtn = document.getElementById('btn-next');
    if (index === this.questions.length - 1) {
      nextBtn.textContent = 'Review & Submit →';
      nextBtn.className = 'btn btn-primary';
    } else {
      nextBtn.textContent = 'Next Question →';
      nextBtn.className = 'btn btn-primary';
    }

    this.updatePaletteStyles();
  }

  navigateTo(index) {
    this.renderQuestion(index);
  }

  next() {
    if (this.currentIndex < this.questions.length - 1) {
      this.renderQuestion(this.currentIndex + 1);
    } else {
      this.showSubmitModal();
    }
  }

  prev() {
    if (this.currentIndex > 0) {
      this.renderQuestion(this.currentIndex - 1);
    }
  }

  toggleFlag() {
    const q = this.questions[this.currentIndex];
    if (this.flagged.has(q.id)) {
      this.flagged.delete(q.id);
    } else {
      this.flagged.add(q.id);
    }
    this.renderQuestion(this.currentIndex);
  }

  startTimer() {
    const timerEl = document.getElementById('timer-display');
    this.timerInterval = setInterval(() => {
      this.timeRemaining--;

      if (timerEl) {
        timerEl.textContent = formatDuration(this.timeRemaining);
        if (this.timeRemaining <= 300) {
          timerEl.style.color = 'var(--danger)';
        }
      }

      if (this.timeRemaining <= 0) {
        clearInterval(this.timerInterval);
        showToast('Exam time elapsed! Submitting assessment...', 'warning');
        this.submitExam(true);
      }
    }, 1000);
  }

  startAutoSave() {
    this.autoSaveInterval = setInterval(async () => {
      const currentQ = this.questions[this.currentIndex];
      if (!currentQ || !this.attemptId || this.attemptId === 'demo-attempt-01') return;

      try {
        const val = this.answers[currentQ.id];
        if (val !== undefined) {
          await api.post(`/learner/attempts/${this.attemptId}/respond`, {
            question_id: currentQ.id,
            selected_option_ids: Array.isArray(val) ? val : (typeof val === 'string' && val.startsWith('opt') ? [val] : null),
            text_response: typeof val === 'string' && !val.startsWith('opt') ? val : null
          });
        }
      } catch (e) {
        // Silently retry next cycle
      }
    }, 30000);
  }

  showSubmitModal() {
    openModal('submit-confirmation-modal');
  }

  async submitExam(auto = false) {
    if (this.timerInterval) clearInterval(this.timerInterval);
    if (this.autoSaveInterval) clearInterval(this.autoSaveInterval);

    try {
      showToast('Submitting and triggering GenAI grading...', 'info');

      if (this.attemptId && this.attemptId !== 'demo-attempt-01') {
        await api.post(`/learner/attempts/${this.attemptId}/submit`, {});
      }

      setTimeout(() => {
        window.location.href = `/learner/exam-result.html?attempt_id=${this.attemptId || 'demo-attempt-01'}`;
      }, 1000);
    } catch (err) {
      showToast('Submission error: ' + err.message, 'error');
    }
  }
}
