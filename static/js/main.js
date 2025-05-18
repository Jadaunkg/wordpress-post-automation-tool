// In static/js/main.js

/**
 * Adds a set of input fields for a new writer to the specified container.
 * @param {string} containerId - The ID of the div element to append writer fields to.
 * @param {object|null} existingAuthor - Optional. Data for an existing author to pre-fill fields.
 * @param {string} formType - 'add' or 'edit', used to prefix IDs for uniqueness.
 */
function addWriterFields(containerId, existingAuthor = null, formType = 'add') {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Writer fields container with ID '${containerId}' not found.`);
        return;
    }

    const writerCount = container.querySelectorAll('.writer-entry').length;
    const writerEntry = document.createElement('div');
    writerEntry.classList.add('writer-entry');
    
    const idPrefix = formType + '_'; 

    const authorId = (existingAuthor && existingAuthor.id) ? existingAuthor.id : `new_${Date.now()}_${writerCount}`;
    const wpUsername = (existingAuthor && existingAuthor.wp_username) ? existingAuthor.wp_username : '';
    const wpUserId = (existingAuthor && existingAuthor.wp_user_id) ? existingAuthor.wp_user_id : '';
    // Application password should NOT be pre-filled for existing authors on edit for security.
    const appPassword = (formType === 'add' && existingAuthor && existingAuthor.app_password) ? existingAuthor.app_password : '';


    writerEntry.innerHTML = `
        <h4>Writer ${writerCount + 1} <button type="button" class="remove-writer-btn" title="Remove this writer"><i class="fas fa-trash-alt"></i> Remove</button></h4>
        <input type="hidden" name="author_id_${writerCount}" value="${authorId}">
        <div class="form-group">
            <label for="${idPrefix}author_wp_username_${writerCount}">WordPress Username:</label>
            <input type="text" id="${idPrefix}author_wp_username_${writerCount}" name="author_wp_username_${writerCount}" class="form-control" value="${wpUsername}" required placeholder="WP Username">
        </div>
        <div class="form-group">
            <label for="${idPrefix}author_wp_user_id_${writerCount}">WordPress User ID:</label>
            <input type="text" id="${idPrefix}author_wp_user_id_${writerCount}" name="author_wp_user_id_${writerCount}" class="form-control" value="${wpUserId}" required placeholder="e.g., 3 (See guidelines)">
        </div>
        <div class="form-group">
            <label for="${idPrefix}author_app_password_${writerCount}">WordPress Application Password:</label>
            <input type="password" id="${idPrefix}author_app_password_${writerCount}" name="author_app_password_${writerCount}" class="form-control" value="${appPassword}" required placeholder="Enter Application Password">
            ${formType === 'edit' ? '<small class="form-text">Leave blank to keep existing password, or enter new to update.</small>' : ''}
        </div>
    `;
    container.appendChild(writerEntry);

    const newRemoveButton = writerEntry.querySelector('.remove-writer-btn');
    if (newRemoveButton) {
        newRemoveButton.addEventListener('click', function() {
            removeWriter(this);
        });
    }
}

/**
 * Removes the parent '.writer-entry' element of the clicked remove button.
 * @param {HTMLElement} button - The remove button element that was clicked.
 */
function removeWriter(button) {
    const writerEntry = button.closest('.writer-entry');
    if (writerEntry) {
        const container = writerEntry.parentElement; // Get container before removing entry
        writerEntry.remove();
        if (container) { // Re-number headings if container still exists
            const remainingEntries = container.querySelectorAll('.writer-entry');
            remainingEntries.forEach((entry, index) => {
                const heading = entry.querySelector('h4');
                if (heading) {
                    const removeBtnHTML = heading.querySelector('.remove-writer-btn') ? heading.querySelector('.remove-writer-btn').outerHTML : '';
                    heading.innerHTML = `Writer ${index + 1} ${removeBtnHTML}`;
                }
            });
        }
    }
}

/**
 * Initializes the author fields management for a given form.
 * @param {string} containerId - ID of the div to hold writer fields.
 * @param {string} addButtonId - ID of the "Add Writer" button.
 * @param {Array} existingAuthorsData - Array of existing author objects (for edit forms).
 * @param {string} formType - 'add' or 'edit'.
 */
function initializeAuthorManagement(containerId, addButtonId, existingAuthorsData = [], formType = 'add') {
    const addAuthorBtn = document.getElementById(addButtonId);
    const container = document.getElementById(containerId);

    if (!addAuthorBtn || !container) {
        return;
    }
    container.querySelectorAll('.writer-entry').forEach(entry => entry.remove());

    if (existingAuthorsData && existingAuthorsData.length > 0) {
        existingAuthorsData.forEach(author => addWriterFields(containerId, author, formType));
    } else {
        if (formType === 'add') { 
             addWriterFields(containerId, null, formType);
        }
    }

    addAuthorBtn.onclick = function() {
        addWriterFields(containerId, null, formType);
    };
}

// --- Main DOMContentLoaded Listener ---
document.addEventListener('DOMContentLoaded', function() {
    console.log("Main JavaScript Initializing...");

    // --- Toggle Add Profile Form Visibility on manage_profiles.html ---
    const toggleBtn = document.getElementById('toggleAddProfileFormBtn');
    const addProfileFormContainer = document.getElementById('addProfileFormContainer');
    const cancelAddProfileBtn = document.getElementById('cancelAddProfileBtn');

    if (toggleBtn && addProfileFormContainer) {
        toggleBtn.addEventListener('click', function() {
            const isHidden = addProfileFormContainer.style.display === 'none' || addProfileFormContainer.style.display === '';
            if (isHidden) {
                addProfileFormContainer.style.display = 'block';
                this.innerHTML = '<i class="fas fa-minus-circle"></i> Hide Add Profile Form';
                addProfileFormContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                addProfileFormContainer.style.display = 'none';
                this.innerHTML = '<i class="fas fa-plus-circle"></i> Add New Profile';
            }
        });
    }
    if (cancelAddProfileBtn && addProfileFormContainer && toggleBtn) {
        cancelAddProfileBtn.addEventListener('click', function() {
            addProfileFormContainer.style.display = 'none';
            toggleBtn.innerHTML = '<i class="fas fa-plus-circle"></i> Add New Profile';
        });
    }

    // --- Initialize Author Fields Management ---
    if (document.getElementById('authorsContainerAdd') && document.getElementById('addAuthorBtn')) {
        initializeAuthorManagement('authorsContainerAdd', 'addAuthorBtn', [], 'add');
    }

    const editAuthorsContainer = document.getElementById('authorsContainerEdit');
    if (editAuthorsContainer && document.getElementById('addAuthorBtnEdit')) {
        try {
            const existingAuthorsJson = editAuthorsContainer.dataset.existingAuthors;
            const existingAuthors = (existingAuthorsJson && existingAuthorsJson !== 'null' && existingAuthorsJson.trim() !== '') ? JSON.parse(existingAuthorsJson) : [];
            initializeAuthorManagement('authorsContainerEdit', 'addAuthorBtnEdit', existingAuthors, 'edit');
        } catch (e) {
            console.error("Error parsing existing authors data for edit form:", e, editAuthorsContainer ? editAuthorsContainer.dataset.existingAuthors : 'Container not found');
            initializeAuthorManagement('authorsContainerEdit', 'addAuthorBtnEdit', [], 'edit');
        }
    }
    
    // --- Report Section Checkbox Controls ---
    function setupReportSectionControls(formPrefix) { 
        const selectAllBtn = document.getElementById('selectAllSections' + formPrefix);
        const unselectAllBtn = document.getElementById('unselectAllSections' + formPrefix);
        const checkboxesContainer = document.getElementById('reportSections' + formPrefix + 'Container');

        if(selectAllBtn && unselectAllBtn && checkboxesContainer) {
            const checkboxes = checkboxesContainer.querySelectorAll('input[type="checkbox"]');
            if (checkboxes.length > 0) {
                selectAllBtn.addEventListener('click', () => checkboxes.forEach(cb => cb.checked = true));
                unselectAllBtn.addEventListener('click', () => checkboxes.forEach(cb => cb.checked = false));
            }
        }
    }
    setupReportSectionControls('Add');
    setupReportSectionControls('Edit');

    // --- Smooth Scroll for Internal Page Links ---
    document.querySelectorAll('.smooth-scroll').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if (targetId && targetId.startsWith('#')) {
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });

    // --- Automation Runner Page Specific JS ---
    if (document.getElementById('automationRunForm')) {
        console.log("Main JS loaded for Automation Runner Page specific enhancements.");

        // Toggle ticker input methods
        window.toggleTickerInput = function(profileId, selectedMethod) {
            const fileSection = document.getElementById(`file_upload_section_${profileId}`);
            const manualSection = document.getElementById(`manual_ticker_section_${profileId}`);
            const fileInput = document.getElementById(`ticker_file_${profileId}`);
            const manualTextarea = document.getElementById(`custom_tickers_${profileId}`);

            if (!fileSection || !manualSection) {
                console.warn(`Ticker input sections not found for profile ${profileId}`);
                return;
            }

            if (selectedMethod === 'file') {
                fileSection.style.display = 'block';
                manualSection.style.display = 'none';
                if (manualTextarea) manualTextarea.value = '';
            } else {
                fileSection.style.display = 'none';
                manualSection.style.display = 'block';
                if (fileInput) fileInput.value = '';

                const fileInfoDiv = document.getElementById(`uploaded_file_info_${profileId}`);
                const tickerTableContainer = document.getElementById(`ticker_table_container_${profileId}`);
                if (fileInfoDiv) fileInfoDiv.style.display = 'none';
                if (tickerTableContainer) tickerTableContainer.style.display = 'none';
            }
        };

        // Default ticker input view
        document.querySelectorAll('.profile-run-card').forEach(card => {
            const profileId = card.dataset.profileId;
            if (profileId) {
                toggleTickerInput(profileId, 'file');
            }
        });

        // Handle file selection and preview
        document.querySelectorAll('.ticker-file-input').forEach(input => {
            input.addEventListener('change', function(event) {
                const profileId = this.dataset.profileId;
                const fileInfoDiv = document.getElementById(`uploaded_file_info_${profileId}`);
                const fileNameSpan = fileInfoDiv ? fileInfoDiv.querySelector('.file-name') : null;
                const removeFileBtn = fileInfoDiv ? fileInfoDiv.querySelector('.remove-file-btn') : null;
                const tickerTableContainer = document.getElementById(`ticker_table_container_${profileId}`);
                const tickerTableBody = tickerTableContainer ? tickerTableContainer.querySelector('tbody') : null;

                if (event.target.files && event.target.files[0]) {
                    const file = event.target.files[0];
                    if (fileNameSpan) fileNameSpan.textContent = file.name;
                    if (fileInfoDiv) fileInfoDiv.style.display = 'flex';

                    if (removeFileBtn) {
                        removeFileBtn.style.display = 'inline-block';
                        removeFileBtn.onclick = function() {
                            input.value = '';
                            fileInfoDiv.style.display = 'none';
                            if (fileNameSpan) fileNameSpan.textContent = '';
                            if (tickerTableContainer) tickerTableContainer.style.display = 'none';
                            if (tickerTableBody) tickerTableBody.innerHTML = '';
                            removeFileBtn.style.display = 'none';
                        };
                    }

                    if (tickerTableContainer && tickerTableBody) {
                        tickerTableBody.innerHTML = `<tr><td colspan="2" style="text-align:center; color:#6c757d; padding:10px;"><i>Preview tickers from '${file.name}'. Status lookup requires backend processing.</i></td></tr>`;
                        tickerTableContainer.style.display = 'block';
                    }

                    const manualTextarea = document.getElementById(`custom_tickers_${profileId}`);
                    if (manualTextarea) manualTextarea.value = '';
                } else {
                    if (fileInfoDiv) fileInfoDiv.style.display = 'none';
                    if (fileNameSpan) fileNameSpan.textContent = '';
                    if (tickerTableContainer) tickerTableContainer.style.display = 'none';
                    if (tickerTableBody) tickerTableBody.innerHTML = '';
                    if (removeFileBtn) removeFileBtn.style.display = 'none';
                }
            });
        });
    }
});
