function confirmDelete() {
    return confirm("Rostan ham o'chirmoqchimisiz?");
}

function changeLanguage(langCode) {
    const currentBtn = event?.currentTarget;
    if (currentBtn) {
        const originalHTML = currentBtn.innerHTML;
        currentBtn.innerHTML = '<span class="loading">⟳</span>';
        currentBtn.disabled = true;
    }

    fetch('/set-language/' + langCode, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                window.location.reload();
            } else {
                window.location.href = '/set-language/' + langCode;
            }
        })
        .catch(error => {
            console.error('Language switch error:', error);
            window.location.href = '/set-language/' + langCode;
        });
}

document.addEventListener('DOMContentLoaded', function () {
    // Animate stats counting (optional)
    const statCards = document.querySelectorAll('.stat-card');

    statCards.forEach((card, index) => {
        card.addEventListener('mouseenter', function () {
            this.style.transform = 'translateY(-5px) scale(1.02)';
        });

        card.addEventListener('mouseleave', function () {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // Add click effects to action buttons
    const actionButtons = document.querySelectorAll('.action-btn');

    actionButtons.forEach(btn => {
        btn.addEventListener('click', function (e) {
            // Add ripple effect
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;

            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.6);
                transform: scale(0);
                animation: ripple 0.6s linear;
                width: ${size}px;
                height: ${size}px;
                left: ${x}px;
                top: ${y}px;
            `;

            this.appendChild(ripple);

            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
});

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
});

function generateQuestionFields() {
    const numQuestions = document.getElementById('num_questions').value;
    const container = document.getElementById('questions_container');
    const template = document.getElementById('question_type_template');

    container.innerHTML = '';

    if (numQuestions > 0) {
        const questionHeader = document.createElement('h3');
        questionHeader.textContent = 'Savollar';
        container.appendChild(questionHeader);

        for (let i = 1; i <= numQuestions; i++) {
            const questionDiv = document.createElement('div');
            questionDiv.className = 'question-item';

            questionDiv.innerHTML = `
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
                </div>
            `;

            container.appendChild(questionDiv);
        }
    }
}

function initMobileMenu() {
    // Completely disable mobile menu functionality
    const hamburgerMenu = document.getElementById('hamburgerMenu');
    const mobileOverlay = document.getElementById('mobileOverlay');
    
    if (hamburgerMenu) {
        hamburgerMenu.style.display = 'none';
    }
    if (mobileOverlay) {
        mobileOverlay.style.display = 'none';
    }
    
    // Ensure navigation is always visible
    const navMenu = document.getElementById('navMenu');
    const navUser = document.getElementById('navUser');
    
    if (navMenu) {
        navMenu.style.display = 'flex';
    }
    if (navUser) {
        navUser.style.display = 'flex';
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const numQuestions = document.getElementById('num_questions');
    if (numQuestions && numQuestions.value) {
        generateQuestionFields();
    }

    initializeEventListeners();
    hideFlashMessagesAfterDelay();
    initMobileMenu();

    forceDesktopViewport();
    initMobileMenu();
    
    // Disable touch gestures that might cause zoom
    document.addEventListener('touchstart', function(e) {
        if (e.touches.length > 1) {
            e.preventDefault();
        }
    }, { passive: false });

    document.addEventListener('gesturestart', function(e) {
        e.preventDefault();
    });

    document.addEventListener('gesturechange', function(e) {
        e.preventDefault();
    });

    document.addEventListener('gestureend', function(e) {
        e.preventDefault();
    });
});

function initializeEventListeners() {
    const closeButtons = document.querySelectorAll('.alert-close');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            this.parentElement.style.display = 'none';
        });
    });

    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function (e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    });

    // Delete confirmation
    const deleteButtons = document.querySelectorAll('form[onsubmit*="confirm"]');
    deleteButtons.forEach(form => {
        form.addEventListener('submit', function (e) {
            if (!confirm('Aniq o\'chirilsinmi?')) {
                e.preventDefault();
            }
        });
    });
}

function forceDesktopViewport() {
    const viewport = document.querySelector('meta[name="viewport"]');
    if (viewport) {
        viewport.setAttribute('content', 'width=1200, initial-scale=1.0, user-scalable=yes');
    }
    
    // Prevent any mobile-specific behavior
    document.body.classList.remove('mobile', 'tablet');
    document.body.classList.add('desktop');
}

// Auto-hide flash messages
function hideFlashMessagesAfterDelay() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.5s ease';
            setTimeout(() => {
                alert.remove();
            }, 500);
        }, 5000);
    });
}

// Form validation function
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;

    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            field.style.borderColor = '#e74c3c';
        } else {
            field.style.borderColor = '#ddd';
        }
    });

    return isValid;
}