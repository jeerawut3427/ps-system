// app.js
// Main application file for initialization and state management.

import { sendRequest } from './api.js';
import * as ui from './ui.js';
import * as handlers from './handlers.js';
import { escapeHTML } from './utils.js';

// --- Global State and DOM References ---
window.currentUser = null;
window.currentWeeklyReports = [];
window.allArchivedReports = {};
window.allHistoryData = {};
window.personnelCurrentPage = 1;
window.userCurrentPage = 1;
window.editingReportData = null;

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
    
    // Elements for Weekly Reporting System (main.html and admin.html)
    window.statusSubmissionListArea = document.getElementById('status-submission-list-area');
    window.submitStatusTitle = document.getElementById('submit-status-title');
    window.submissionFormSection = document.getElementById('submission-form-section');
    window.reviewReportSection = document.getElementById('review-report-section');
    window.reviewListArea = document.getElementById('review-list-area');
    window.backToFormBtn = document.getElementById('back-to-form-btn');
    window.confirmSubmitBtn = document.getElementById('confirm-submit-btn');
    window.reviewStatusBtn = document.getElementById('review-status-btn');
    window.reportContainer = document.getElementById('report-container');
    window.exportArchiveBtn = document.getElementById('export-archive-btn');
    window.archiveContainer = document.getElementById('archive-container');
    window.archiveYearSelect = document.getElementById('archive-year-select');
    window.archiveMonthSelect = document.getElementById('archive-month-select');
    window.showArchiveBtn = document.getElementById('show-archive-btn');
    window.archiveConfirmModal = document.getElementById('archive-confirm-modal');
    window.cancelArchiveBtn = document.getElementById('cancel-archive-btn');
    window.confirmArchiveBtn = document.getElementById('confirm-archive-btn');
    window.historyContainer = document.getElementById('history-container');
    window.historyYearSelect = document.getElementById('history-year-select');
    window.historyMonthSelect = document.getElementById('history-month-select');
    window.showHistoryBtn = document.getElementById('show-history-btn');
    window.activeStatusesContainer = document.getElementById('active-statuses-container');
    
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
    window.personnelSearchInput = document.getElementById('personnel-search-input');
    window.userSearchInput = document.getElementById('user-search-input');
}

// --- Main Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    assignDomElements();
    
    try {
        window.currentUser = JSON.parse(localStorage.getItem('currentUser'));
    } catch (e) {
        window.currentUser = null;
    }

    if (!window.currentUser) {
        localStorage.removeItem('currentUser');
        window.location.href = '/login.html';
        return;
    }
    
    initializePage();
});

function initializePage() {
    appContainer.classList.remove('hidden');
    const userRole = currentUser.role;
    welcomeMessage.textContent = `ล็อกอินในฐานะ: ${escapeHTML(currentUser.username)} (${escapeHTML(userRole)})`;
    const backToSelectionBtn = document.getElementById('back-to-selection-btn');
    if (backToSelectionBtn) {
        backToSelectionBtn.addEventListener('click', () => {
            window.location.href = '/selection.html';
        });
    }

    const is_admin = (userRole === 'admin');
    
    // Determine which page we are on
    const onAdminPage = !!document.getElementById('pane-personnel');

    if (onAdminPage) {
       // This logic is now in admin.js
    } else { // On main.html
        document.getElementById('tab-dashboard').classList.toggle('hidden', !is_admin);
        document.getElementById('tab-active-statuses').classList.remove('hidden');
        document.getElementById('tab-submit-status').classList.remove('hidden');
        document.getElementById('tab-history').classList.remove('hidden');
        document.getElementById('tab-report').classList.toggle('hidden', !is_admin);
        document.getElementById('tab-archive').classList.toggle('hidden', !is_admin);
        if (is_admin) {
            switchTab('tab-dashboard');
        } else {
            switchTab('tab-active-statuses');
        }
    }

    logoutBtn.addEventListener('click', () => performLogout());

    window.addEventListener('mousemove', resetInactivityTimer);
    window.addEventListener('keydown', resetInactivityTimer);
    window.addEventListener('click', resetInactivityTimer);
    resetInactivityTimer();

    tabs.forEach(tab => tab.addEventListener('click', () => switchTab(tab.id)));
    
    // Event listeners for weekly reporting system
    if (reviewStatusBtn) reviewStatusBtn.addEventListener('click', handlers.handleReviewStatus);
    if (backToFormBtn) backToFormBtn.addEventListener('click', () => {
        reviewReportSection.classList.add('hidden');
        submissionFormSection.classList.remove('hidden');
    });
    if (confirmSubmitBtn) confirmSubmitBtn.addEventListener('click', handlers.handleSubmitStatusReport);
    if (exportArchiveBtn) exportArchiveBtn.addEventListener('click', () => {
        if (!currentWeeklyReports || currentWeeklyReports.length === 0) {
            ui.showMessage('ไม่มีข้อมูลรายงานที่จะส่งออก', false);
            return;
        }
        archiveConfirmModal.classList.add('active');
    });
    if (cancelArchiveBtn) cancelArchiveBtn.addEventListener('click', () => archiveConfirmModal.classList.remove('active'));
    if (confirmArchiveBtn) confirmArchiveBtn.addEventListener('click', handlers.handleExportAndArchive);
    
    if (showArchiveBtn) showArchiveBtn.addEventListener('click', handlers.handleShowArchive);
    if (archiveContainer) archiveContainer.addEventListener('click', handlers.handleArchiveDownloadClick);
    
    if (archiveYearSelect) {
        archiveYearSelect.addEventListener('change', () => {
            const selectedYear = archiveYearSelect.value;
            archiveMonthSelect.innerHTML = '<option value="">เลือกเดือน</option>';
            if (selectedYear && allArchivedReports[selectedYear]) {
                const sortedMonths = Object.keys(allArchivedReports[selectedYear]).sort((a, b) => b - a);
                sortedMonths.forEach(month => {
                    const option = document.createElement('option');
                    option.value = month;
                    option.textContent = new Date(2000, parseInt(month) - 1, 1).toLocaleString('th-TH', { month: 'long' });
                    archiveMonthSelect.appendChild(option);
                });
            }
        });
    }

    if (showHistoryBtn) showHistoryBtn.addEventListener('click', handlers.handleShowHistory);
    
    if (historyYearSelect) {
        historyYearSelect.addEventListener('change', () => {
            const selectedYear = historyYearSelect.value;
            historyMonthSelect.innerHTML = '<option value="">เลือกเดือน</option>';
            if (selectedYear && window.allHistoryData[selectedYear]) {
                const sortedMonths = Object.keys(window.allHistoryData[selectedYear]).sort((a, b) => b - a);
                sortedMonths.forEach(month => {
                    const option = document.createElement('option');
                    option.value = month;
                    option.textContent = new Date(2000, parseInt(month) - 1, 1).toLocaleString('th-TH', { month: 'long' });
                    historyMonthSelect.appendChild(option);
                });
            }
        });
    }

    if(historyContainer) historyContainer.addEventListener('click', handlers.handleHistoryEditClick);
    if(reportContainer) reportContainer.addEventListener('click', handlers.handleWeeklyReportEditClick);

    if (statusSubmissionListArea) {
        statusSubmissionListArea.addEventListener('click', function(e) {
            if (e.target && e.target.classList.contains('add-status-btn')) {
                ui.addStatusRow(e.target);
            }
            if (e.target && e.target.classList.contains('remove-status-btn')) {
                const subRow = e.target.closest('tr');
                if (subRow) {
                    subRow.remove();
                }
            }
        });
    }
}

// --- Data Loading and Tab Switching ---
window.loadDataForPane = async function(paneId) {
    let payload = {};
    const actions = {
        'pane-dashboard': { action: 'get_dashboard_summary', renderer: ui.renderDashboard },
        'pane-active-statuses': { action: 'get_active_statuses', renderer: ui.renderActiveStatuses },
        'pane-submit-status': { action: 'list_personnel', renderer: ui.renderStatusSubmissionForm, fetchAll: true },
        'pane-history': { action: 'get_submission_history', renderer: ui.renderSubmissionHistory },
        'pane-report': { action: 'get_status_reports', renderer: ui.renderWeeklyReport },
        'pane-archive': { action: 'get_archived_reports', renderer: (res) => {
            const archives = res.archives;
            window.allArchivedReports = archives || {};
            ui.populateArchiveSelectors(window.allArchivedReports);
            if(window.archiveContainer) window.archiveContainer.innerHTML = '';
        }}
    };

    const paneConfig = actions[paneId];
    if (!paneConfig) return;

    if (paneConfig.fetchAll) {
        payload.fetchAll = true;
    }

    if (paneId === 'pane-submit-status' && window.currentUser.role === 'admin') {
        const deptSelector = document.getElementById('admin-dept-selector');
        if (deptSelector && deptSelector.value) {
            payload.department = deptSelector.value;
        }
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
    
    // Load data for the newly activated tab
    loadDataForPane(paneId);
}

