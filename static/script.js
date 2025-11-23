function confirmDelete() {
    return confirm("Rostan ham o'chirmoqchimisiz?");
}

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
    const hamburgerMenu = document.getElementById('hamburgerMenu');
    const navMenu = document.getElementById('navMenu');
    const navUser = document.getElementById('navUser');
    const mobileOverlay = document.getElementById('mobileOverlay');
    const settingsDropdown = document.getElementById('settingsDropdown');
    
    if (!hamburgerMenu) return;
    
    function toggleMobileMenu() {
        const isActive = hamburgerMenu.classList.contains('active');
        
        hamburgerMenu.classList.toggle('active');
        navMenu.classList.toggle('active');
        navUser.classList.toggle('active');
        mobileOverlay.classList.toggle('active');
        
        // Prevent body scroll when menu is open
        if (!isActive) {
            document.body.classList.add('menu-open');
        } else {
            document.body.classList.remove('menu-open');
        }
    }
    
    function closeMobileMenu() {
        hamburgerMenu.classList.remove('active');
        navMenu.classList.remove('active');
        navUser.classList.remove('active');
        mobileOverlay.classList.remove('active');
        document.body.classList.remove('menu-open');
        
        // Close dropdowns
        if (settingsDropdown) {
            settingsDropdown.classList.remove('active');
        }
    }
    
    // Hamburger menu click
    hamburgerMenu.addEventListener('click', function(e) {
        e.stopPropagation();
        toggleMobileMenu();
    });
    
    // Overlay click
    mobileOverlay.addEventListener('click', closeMobileMenu);
    
    // Settings dropdown for mobile
    if (settingsDropdown) {
        const dropdownLink = settingsDropdown.querySelector('.nav-link');
        
        dropdownLink.addEventListener('click', function(e) {
            if (window.innerWidth <= 768) {
                e.preventDefault();
                e.stopPropagation();
                settingsDropdown.classList.toggle('active');
            }
        });
    }
    
    // Close menu when clicking on regular nav links (not dropdown toggle)
    document.querySelectorAll('.nav-menu > .nav-link:not(.nav-dropdown .nav-link)').forEach(link => {
        link.addEventListener('click', closeMobileMenu);
    });
    
    // Close menu when clicking on dropdown links
    document.querySelectorAll('.dropdown-link').forEach(link => {
        link.addEventListener('click', closeMobileMenu);
    });
    
    // Close menu on window resize to desktop
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            if (window.innerWidth > 768) {
                closeMobileMenu();
            }
        }, 250);
    });
    
    // Prevent menu from staying open on orientation change
    window.addEventListener('orientationchange', function() {
        setTimeout(closeMobileMenu, 300);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const numQuestions = document.getElementById('num_questions');
    if (numQuestions && numQuestions.value) {
        generateQuestionFields();
    }
    
    initializeEventListeners();
    hideFlashMessagesAfterDelay();
    initMobileMenu();
});

function initializeEventListeners() { 
    const closeButtons = document.querySelectorAll('.alert-close'); 
    closeButtons.forEach(btn => { 
        btn.addEventListener('click', function() { 
            this.parentElement.style.display = 'none'; 
        }); 
    });

    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            }
        });
    });

    // Delete confirmation
    const deleteButtons = document.querySelectorAll('form[onsubmit*="confirm"]');
    deleteButtons.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!confirm('Aniq o\'chirilsinmi?')) {
                e.preventDefault();
            }
        });
    });
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