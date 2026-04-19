/* TeacherPro — shared front-end behaviour */

/* ---- Theme management ---- */
var _SUN = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
var _MOON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

function _applyThemeBtn() {
    var btn = document.getElementById('themeToggle');
    if (!btn) return;
    var t = document.documentElement.getAttribute('data-theme') || 'dark';
    btn.innerHTML = t === 'dark' ? _SUN : _MOON;
    btn.title = t === 'dark' ? "Yorug' rejim" : "Qorong'i rejim";
}

function toggleTheme() {
    var curr = document.documentElement.getAttribute('data-theme') || 'dark';
    var next = curr === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    _applyThemeBtn();
}

function confirmDelete() {
    return confirm("Rostan ham o'chirmoqchimisiz?");
}

function changeLanguage(langCode) {
    const currentBtn = event?.currentTarget;
    if (currentBtn) {
        currentBtn.innerHTML = '<span class="loading">⟳</span>';
        currentBtn.disabled = true;
    }
    const rootPath = window.ROOT_PATH || '';
    fetch(rootPath + '/set-language/' + langCode, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') { window.location.reload(); }
            else { window.location.href = rootPath + '/set-language/' + langCode; }
        })
        .catch(() => { window.location.href = rootPath + '/set-language/' + langCode; });
}

/* Language dropdown toggle + theme button init */
document.addEventListener('DOMContentLoaded', function () {
    const languageCurrent = document.getElementById('languageCurrent');
    const languageDropdown = document.getElementById('languageDropdown');
    if (languageCurrent && languageDropdown) {
        languageCurrent.addEventListener('click', function (e) {
            e.stopPropagation();
            languageDropdown.classList.toggle('show');
        });
        document.addEventListener('click', function () {
            languageDropdown.classList.remove('show');
        });
    }

    /* Theme toggle */
    _applyThemeBtn();
    var themeBtn = document.getElementById('themeToggle');
    if (themeBtn) themeBtn.addEventListener('click', toggleTheme);
});

/* create_exam.html calls this when questions count changes */
function generateQuestionFields() {
    const numQuestions = document.getElementById('num_questions').value;
    const container = document.getElementById('questions_container');
    const template = document.getElementById('question_type_template');
    container.innerHTML = '';
    if (numQuestions > 0) {
        const h = document.createElement('h3');
        h.textContent = 'Savollar';
        container.appendChild(h);
        for (let i = 1; i <= numQuestions; i++) {
            const q = document.createElement('div');
            q.className = 'question-item';
            q.innerHTML = `
                <h4>${i}-savol</h4>
                <div class="form-row">
                    <div class="form-group">
                        <label for="question_type_${i}">Savol turi *</label>
                        <select id="question_type_${i}" name="question_type_${i}" required>
                            ${template.innerHTML}
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="max_score_${i}">Maksimal ball *</label>
                        <input type="number" id="max_score_${i}" name="max_score_${i}"
                               step="0.1" min="0.1" required>
                    </div>
                </div>`;
            container.appendChild(q);
        }
    }
}

/* Auto-hide flashes */
function hideFlashMessagesAfterDelay() {
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity .5s ease';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });
}

/* Simple form validation */
function validateForm(form) {
    let ok = true;
    form.querySelectorAll('[required]').forEach(field => {
        if (!field.value.trim()) {
            ok = false;
            field.style.borderColor = 'oklch(70% 0.20 22)';
        } else {
            field.style.borderColor = '';
        }
    });
    return ok;
}

function initializeEventListeners() {
    document.querySelectorAll('.alert-close').forEach(btn => {
        btn.addEventListener('click', function () { this.parentElement.style.display = 'none'; });
    });
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function (e) {
            if (!validateForm(this)) e.preventDefault();
        });
    });
    document.querySelectorAll('form[onsubmit*="confirm"]').forEach(form => {
        form.addEventListener('submit', function (e) {
            if (!confirm("Aniq o'chirilsinmi?")) e.preventDefault();
        });
    });
}

document.addEventListener('DOMContentLoaded', function () {
    const numQuestions = document.getElementById('num_questions');
    if (numQuestions && numQuestions.value) generateQuestionFields();
    initializeEventListeners();
    hideFlashMessagesAfterDelay();
});
