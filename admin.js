// admin.js
// Logic for the dedicated admin page (admin.html).

import { sendRequest } from './api.js';
import * as ui from './ui.js';
import * as handlers from './handlers.js';
import { escapeHTML } from './utils.js';

// --- Global State and DOM References ---
window.currentUser = null;
window.personnelCurrentPage = 1;
window.userCurrentPage = 1;

// --- Auto Logout Feature ---
let inactivityTimer;
const INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes

function performLogout() {
    clearTimeout(inactivityTimer);
    sendRequest('logout', {}).finally(() => {
        localStorage.removeItem('currentUser');
        window.location.href = '/login.html';
    });
}

function autoLogoutUser() {
    alert("คุณไม่มีการใช้งานเป็นเวลานาน ระบบจะทำการออกจากระบบเพื่อความปลอดภัย");
    performLogout();
}

function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    inactivityTimer = setTimeout(autoLogoutUser, INACTIVITY_TIMEOUT_MS);
}

// DOM Elements
function assignDomElements() {
    window.appContainer = document.getElementById('app-container');
    window.messageArea = document.getElementById('message-area');
    window.welcomeMessage = document.getElementById('welcome-message');
    window.logoutBtn = document.getElementById('logout-btn');
    window.tabs = document.querySelectorAll('.tab-button');
    window.panes = document.querySelectorAll('.tab-pane');
    
    // Elements for Admin Page (admin.html)
    window.personnelListArea = document.getElementById('personnel-list-area');
    window.addPersonnelBtn = document.getElementById('add-personnel-btn');
    window.personnelModal = document.getElementById('personnel-modal');
    window.personnelForm = document.getElementById('personnel-form');
    window.cancelPersonnelBtn = document.getElementById('cancel-personnel-btn');
    window.importExcelBtn = document.getElementById('import-excel-btn');
    window.excelImportInput = document.getElementById('excel-import-input');
    window.userListArea = document.getElementById('user-list-area');
    window.addUserBtn = document.getElementById('add-user-btn');
    window.userModal = document.getElementById('user-modal');
    window.userForm = document.getElementById('user-form');
    window.cancelUserBtn = document.getElementById('cancel-user-btn');
    window.userModalTitle = document.getElementById('user-modal-title');
}

// --- Main Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    assignDomElements();
    
    try {
        window.currentUser = JSON.parse(localStorage.getItem('currentUser'));
    } catch (e) {
        window.currentUser = null;
    }

    if (!window.currentUser || window.currentUser.role !== 'admin') {
        localStorage.removeItem('currentUser');
        window.location.href = '/login.html'; // Redirect non-admins
        return;
    }
    
    initializePage();
});

function initializePage() {
    appContainer.classList.remove('hidden');
    welcomeMessage.textContent = `ล็อกอินในฐานะ: ${escapeHTML(window.currentUser.username)} (admin)`;
    
    const backToSelectionBtn = document.getElementById('back-to-selection-btn');
    if (backToSelectionBtn) {
        backToSelectionBtn.addEventListener('click', () => {
            window.location.href = '/selection.html';
        });
    }

    ui.populateRankDropdowns();
    document.getElementById('tab-personnel').classList.remove('hidden');
    document.getElementById('tab-admin').classList.remove('hidden');
    switchTab('tab-personnel');
    
    logoutBtn.addEventListener('click', () => performLogout());

    window.addEventListener('mousemove', resetInactivityTimer);
    window.addEventListener('keydown', resetInactivityTimer);
    window.addEventListener('click', resetInactivityTimer);
    resetInactivityTimer();

    tabs.forEach(tab => tab.addEventListener('click', () => switchTab(tab.id)));
    
    // Event listeners for admin page elements
    if(addPersonnelBtn) addPersonnelBtn.addEventListener('click', () => ui.openPersonnelModal());
    if(cancelPersonnelBtn) cancelPersonnelBtn.addEventListener('click', () => personnelModal.classList.remove('active'));
    if(personnelForm) personnelForm.addEventListener('submit', handlers.handlePersonnelFormSubmit);
    if(personnelListArea) personnelListArea.addEventListener('click', handlers.handlePersonnelListClick);
    
    if(addUserBtn) addUserBtn.addEventListener('click', () => ui.openUserModal());
    if(cancelUserBtn) cancelUserBtn.addEventListener('click', () => userModal.classList.remove('active'));
    if(userForm) userForm.addEventListener('submit', handlers.handleUserFormSubmit);
    if(userListArea) userListArea.addEventListener('click', handlers.handleUserListClick);
    
    if(importExcelBtn) importExcelBtn.addEventListener('click', () => excelImportInput.click());
    if(excelImportInput) excelImportInput.addEventListener('change', handlers.handleExcelImport);

    // Setup improved search functionality
    setupSearch('personnel-search-input', 'personnel-clear-search-btn', 'pane-personnel');
    setupSearch('user-search-input', 'user-clear-search-btn', 'pane-admin');
}

// --- Enhanced Search Functionality ---
function setupSearch(inputId, clearBtnId, paneId) {
    const searchInput = document.getElementById(inputId);
    const clearBtn = document.getElementById(clearBtnId);
    let debounceTimer;

    const performSearch = () => {
        if (paneId === 'pane-personnel') {
            window.personnelCurrentPage = 1;
        } else if (paneId === 'pane-admin') {
            window.userCurrentPage = 1;
        }
        loadDataForPane(paneId);
    };

    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        clearBtn.classList.toggle('hidden', !searchInput.value);
        debounceTimer = setTimeout(performSearch, 300); // 300ms delay
    });

    searchInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') {
            clearTimeout(debounceTimer);
            performSearch();
        }
    });

    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.classList.add('hidden');
        performSearch();
        searchInput.focus();
    });
}


// --- Data Loading and Tab Switching ---
window.loadDataForPane = async function(paneId) {
    let payload = {};
    const actions = {
        'pane-personnel': { action: 'list_personnel', renderer: ui.renderPersonnel, searchInputId: 'personnel-search-input', pageState: 'personnelCurrentPage' },
        'pane-admin': { action: 'list_users', renderer: ui.renderUsers, searchInputId: 'user-search-input', pageState: 'userCurrentPage' },
    };

    const paneConfig = actions[paneId];
    if (!paneConfig) return;

    if (paneConfig.searchInputId) {
        payload.searchTerm = document.getElementById(paneConfig.searchInputId).value;
    }
    if (paneConfig.pageState) {
        payload.page = window[paneConfig.pageState];
    }

    try {
        const res = await sendRequest(paneConfig.action, payload);
        if (res && res.status === 'success') {
            if (paneConfig.renderer) {
                paneConfig.renderer(res);
            }
        } else if (res && res.message) {
            ui.showMessage(res.message, false);
        }
    } catch (error) {
        ui.showMessage(error.message, false);
    }
}

window.switchTab = function(tabId) {
    const clickedTab = document.getElementById(tabId);
    if (!clickedTab) return;
    const paneId = tabId.replace('tab-', 'pane-');

    // If the clicked tab is already active, just reload its data.
    if (clickedTab.classList.contains('active')) {
        loadDataForPane(paneId);
        return; 
    }

    // If a different tab is clicked, switch tabs.
    tabs.forEach(tab => {
        const currentPaneId = tab.id.replace('tab-', 'pane-');
        const pane = document.getElementById(currentPaneId);
        if(!pane) return;

        const isActive = (tab.id === tabId);
        tab.classList.toggle('active', isActive);
        pane.classList.toggle('hidden', !isActive);
    });

    // Reset pagination only when switching to a new tab
    if (paneId === 'pane-personnel') window.personnelCurrentPage = 1;
    if (paneId === 'pane-admin') window.userCurrentPage = 1;
    
    // Load data for the newly activated tab
    loadDataForPane(paneId);
}

