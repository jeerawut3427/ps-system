// app_daily.js
// Main application file for the DAILY reporting system.

import { sendRequest } from './api.js';
import { escapeHTML, formatThaiDateArabic, formatThaiDateRangeArabic } from './utils.js';
import { showMessage, createEmptyState } from './ui.js';

// --- Global State and DOM References ---
let currentUser = null;
let fullDailyStatusDataCache = null; // Cache for daily status data
let fullDailyPersistentStatusDataCache = null; // Cache for persistent status data

// --- Chart Color Constants ---
const DAILY_CHART_COLORS = { 'มาปฏิบัติงาน': '#10B981', 'ไม่มาปฏิบัติงาน': '#EF4444', 'ยังไม่ส่งรายงาน': '#A0AEC0' };
const PERSISTENT_CHART_COLORS = { 'ว่าง': '#4CAF50', 'ราชการ': '#3B82F6', 'คุมงาน': '#6366F1', 'ศึกษา': '#8B5CF6', 'ลากิจ': '#EF4444', 'ลาพักผ่อน': '#10B981' };
const STATUS_COLORS = { 'ราชการ': 'bg-blue-50', 'คุมงาน': 'bg-indigo-50', 'ศึกษา': 'bg-purple-50', 'ลากิจ': 'bg-red-50', 'ลาพักผ่อน': 'bg-green-50' };


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

// --- DOM Element Management ---
let appContainer, messageArea, welcomeMessage, logoutBtn, tabs, panes;
let statusSubmissionListArea, submitStatusTitle, submissionFormSection, reviewReportSection, reviewListArea;
let backToFormBtn, confirmSubmitBtn, reviewStatusBtn;
let historyContainer, showHistoryBtn;
let summaryContainer, exportExcelBtn;


function assignDomElements() {
    appContainer = document.getElementById('app-container');
    messageArea = document.getElementById('message-area');
    welcomeMessage = document.getElementById('welcome-message');
    logoutBtn = document.getElementById('logout-btn');
    tabs = document.querySelectorAll('.tab-button');
    panes = document.querySelectorAll('.tab-pane');

    // Daily specific elements
    statusSubmissionListArea = document.getElementById('status-submission-list-area');
    submitStatusTitle = document.getElementById('submit-status-title');
    submissionFormSection = document.getElementById('submission-form-section');
    reviewReportSection = document.getElementById('review-report-section');
    reviewListArea = document.getElementById('review-list-area');
    backToFormBtn = document.getElementById('back-to-form-btn');
    confirmSubmitBtn = document.getElementById('confirm-submit-btn');
    reviewStatusBtn = document.getElementById('review-status-btn');
    historyContainer = document.getElementById('history-container');
    showHistoryBtn = document.getElementById('show-history-btn');
    summaryContainer = document.getElementById('summary-container');
    exportExcelBtn = document.getElementById('export-excel-btn');
}


// --- Main Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    assignDomElements();
    
    try {
        currentUser = JSON.parse(localStorage.getItem('currentUser'));
    } catch (e) {
        currentUser = null;
    }

    if (!currentUser) {
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
    
    // Safely toggle visibility of admin-only tabs
    const dashboardTab = document.getElementById('tab-dashboard-daily');
    if (dashboardTab) dashboardTab.classList.toggle('hidden', !is_admin);
    
    const statusTab = document.getElementById('tab-status-daily');
    if (statusTab) statusTab.classList.toggle('hidden', !is_admin);
    
    const summaryTab = document.getElementById('tab-summary-daily');
    if (summaryTab) summaryTab.classList.toggle('hidden', !is_admin);

    if (is_admin) {
        switchTab('tab-dashboard-daily');
    } else {
        switchTab('tab-submit-status-daily');
    }
    
    logoutBtn.addEventListener('click', () => performLogout());

    window.addEventListener('mousemove', resetInactivityTimer);
    window.addEventListener('keydown', resetInactivityTimer);
    window.addEventListener('click', resetInactivityTimer);
    resetInactivityTimer();

    tabs.forEach(tab => tab.addEventListener('click', () => switchTab(tab.id)));
    
    if (reviewStatusBtn) reviewStatusBtn.addEventListener('click', handleReviewStatus);
    if (backToFormBtn) backToFormBtn.addEventListener('click', () => {
        reviewReportSection.classList.add('hidden');
        submissionFormSection.classList.remove('hidden');
    });
    if (confirmSubmitBtn) confirmSubmitBtn.addEventListener('click', handleSubmitStatusReport);
    if (showHistoryBtn) showHistoryBtn.addEventListener('click', () => loadDataForPane('pane-history-daily'));
    if (exportExcelBtn) exportExcelBtn.addEventListener('click', handleExportDailyReport);
}

// --- UI Rendering ---
function renderDailyDashboard(res) {
    const summary = res.summary;
    if (!summary) return;
    
    document.getElementById('daily-dashboard-date').textContent = formatThaiDateArabic(summary.date);
    document.getElementById('daily-dashboard-total-personnel').textContent = summary.total_personnel || '0';
    
    const presentCount = summary.status_summary['มาปฏิบัติงาน'] || 0;
    const absentCount = summary.status_summary['ไม่มาปฏิบัติงาน'] || 0;
    
    document.getElementById('daily-dashboard-present').textContent = presentCount;
    document.getElementById('daily-dashboard-absent').textContent = absentCount;
    
    const deptStatusArea = document.getElementById('daily-dashboard-department-status');
    deptStatusArea.innerHTML = '';

    if (summary.all_departments && summary.all_departments.length > 0) {
        summary.all_departments.forEach(dept => {
            const submission = summary.submitted_info[dept];
            const isSubmitted = !!submission;
            const card = document.createElement('div');
            card.className = `p-3 rounded-lg border ${isSubmitted ? 'bg-green-100 border-green-300' : 'bg-red-100 border-red-300'}`;
            
            let statusLine = isSubmitted ? `<p class="text-xs text-green-600">ส่งแล้ว</p>` : `<p class="text-xs text-red-600">ยังไม่ส่ง</p>`;
            let detailsLine = isSubmitted ? `<p class="text-xs text-gray-500 mt-1">โดย: ${escapeHTML(submission.submitter_fullname)} (${new Date(submission.timestamp).toLocaleString('th-TH', { timeStyle: 'short' })} น.)</p>` : '';

            card.innerHTML = `<p class="font-semibold text-sm ${isSubmitted ? 'text-green-800' : 'text-red-800'}">${escapeHTML(dept)}</p>${statusLine}${detailsLine}`;
            deptStatusArea.appendChild(card);
        });
    } else {
        deptStatusArea.innerHTML = '<p class="text-gray-500 col-span-full">ไม่พบข้อมูลแผนก</p>';
    }
}

function renderDailySubmissionForm(res) {
    const { personnel, submission_status, all_departments } = res;
    const submissionInfoArea = document.getElementById('submission-info-area');
    const adminSelectorContainer = document.getElementById('admin-dept-selector-container');

    if (!submissionFormSection || !submissionInfoArea || !statusSubmissionListArea || !submitStatusTitle || !adminSelectorContainer) return;
    
    if (currentUser.role !== 'admin' && submission_status) {
        const submittedTime = new Date(submission_status.timestamp).toLocaleString('th-TH');
        submissionInfoArea.innerHTML = `คุณได้ส่งยอดสำหรับวันนี้ไปแล้วเมื่อ ${submittedTime} น.`;
        submissionInfoArea.classList.remove('hidden');
        submissionFormSection.classList.add('hidden');
        adminSelectorContainer.classList.add('hidden');
        submitStatusTitle.textContent = `สถานะการส่งยอดประจำวัน`;
        return;
    }
    
    submissionInfoArea.classList.add('hidden');
    submissionFormSection.classList.remove('hidden');

    const displayPersonnelForDept = (dept) => {
        submitStatusTitle.textContent = `ส่งยอดกำลังพลประจำวัน แผนก ${escapeHTML(dept)}`;
        statusSubmissionListArea.innerHTML = '';
        
        const personnelInDept = personnel.filter(p => p.department === dept);

        if (personnelInDept.length === 0) {
            statusSubmissionListArea.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-gray-500">ไม่พบข้อมูลกำลังพลในแผนกนี้</td></tr>';
            return;
        }

        personnelInDept.forEach((p, index) => {
            const row = document.createElement('tr');
            row.dataset.personnelId = escapeHTML(p.id);
            row.dataset.personnelName = `${escapeHTML(p.rank)} ${escapeHTML(p.first_name)} ${escapeHTML(p.last_name)}`;
            row.innerHTML = `
                <td class="px-4 py-2">${index + 1}</td>
                <td class="px-4 py-2 font-semibold">${row.dataset.personnelName}</td>
                <td class="px-4 py-2">
                    <select class="status-select w-full border rounded px-2 py-1 bg-white">
                        <option value="มาปฏิบัติงาน">มาปฏิบัติงาน</option>
                        <option value="ไม่มาปฏิบัติงาน">ไม่มาปฏิบัติงาน</option>
                    </select>
                </td>
                <td class="px-4 py-2"><input type="text" class="details-input w-full border rounded px-2 py-1" placeholder="หมายเหตุ..."></td>
            `;
            statusSubmissionListArea.appendChild(row);
        });
    };

    if (currentUser.role === 'admin') {
        adminSelectorContainer.classList.remove('hidden');
        adminSelectorContainer.innerHTML = '';
        const label = document.createElement('label');
        label.className = 'block text-sm font-medium text-gray-700 mb-1';
        label.textContent = 'เลือกแผนกเพื่อส่งยอด';
        const selector = document.createElement('select');
        selector.id = 'admin-dept-selector';
        selector.className = 'w-full md:w-1/3 border rounded px-2 py-2 bg-white shadow-sm';
        
        all_departments.forEach(dept => {
            const option = document.createElement('option');
            option.value = dept;
            option.textContent = dept;
            selector.appendChild(option);
        });
        
        adminSelectorContainer.appendChild(label);
        adminSelectorContainer.appendChild(selector);
        
        displayPersonnelForDept(selector.value);

        selector.addEventListener('change', async (e) => {
            const selectedDept = e.target.value;
            const res = await sendRequest('get_personnel_for_daily_report', { department: selectedDept });
            if (res.status === 'success') {
                renderDailySubmissionForm(res); // Re-render the whole form section
            }
        });

    } else {
        adminSelectorContainer.classList.add('hidden');
        displayPersonnelForDept(currentUser.department);
    }
}

function renderDailyHistory(res) {
    if (!historyContainer) return;
    historyContainer.innerHTML = '';
    const history = res.history;

    if (!history || Object.keys(history).length === 0) {
        historyContainer.innerHTML = createEmptyState('ยังไม่มีประวัติการส่งรายงานประจำวัน');
        return;
    }

    const sortedDates = Object.keys(history).sort((a, b) => new Date(b) - new Date(a));

    sortedDates.forEach(date => {
        const reportsForDate = history[date];
        const dateCard = document.createElement('div');
        dateCard.className = 'mb-6 p-4 border rounded-lg bg-gray-50';
        
        let reportsHtml = '';
        reportsForDate.forEach(report => {
            const itemsHtml = report.items.map((item, index) => `
                <tr class="border-t">
                    <td class="py-2 pr-2 text-center">${index + 1}</td>
                    <td class="py-2 px-2">${escapeHTML(item.personnel_name)}</td>
                    <td class="py-2 px-2 ${item.status === 'มาปฏิบัติงาน' ? 'text-green-600' : 'text-red-600'}">${escapeHTML(item.status)}</td>
                    <td class="py-2 px-2 text-gray-600">${escapeHTML(item.details) || '-'}</td>
                </tr>`).join('');

            reportsHtml += `<div class="mt-4">
                <div class="text-sm text-gray-500 mb-2">ส่งเมื่อ: ${new Date(report.timestamp).toLocaleString('th-TH')}</div>
                <table class="min-w-full bg-white text-sm">
                    <thead>
                        <tr>
                            <th class="text-center font-medium text-gray-500 uppercase pb-1 w-[5%]">ลำดับ</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[40%]">ชื่อ-สกุล</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[20%]">สถานะ</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[35%]">หมายเหตุ</th>
                        </tr>
                    </thead>
                    <tbody>${itemsHtml}</tbody>
                </table>
            </div>`;
        });
        dateCard.innerHTML = `<h3 class="text-lg font-semibold text-gray-800">ประวัติการส่ง วันที่ ${formatThaiDateArabic(date)}</h3>${reportsHtml}`;
        historyContainer.appendChild(dateCard);
    });
}

function renderDailySummary(res) {
    if (!summaryContainer) return;
    summaryContainer.innerHTML = '';
    const { all_departments, submitted_info, date } = res.summary;
    
    document.getElementById('summary-date').textContent = formatThaiDateArabic(date);

    if (!all_departments || all_departments.length === 0) {
        summaryContainer.innerHTML = createEmptyState('ไม่พบข้อมูลแผนก');
        return;
    }
    
    all_departments.forEach(dept => {
        const submission = submitted_info[dept];
        const isSubmitted = !!submission;
        const card = document.createElement('div');
        card.className = `p-3 rounded-lg border ${isSubmitted ? 'bg-green-100 border-green-300' : 'bg-red-100 border-red-300'}`;
        
        let statusLine = isSubmitted ? `<p class="text-xs text-green-600">ส่งแล้ว</p>` : `<p class="text-xs text-red-600">ยังไม่ส่ง</p>`;
        let detailsLine = isSubmitted ? `<p class="text-xs text-gray-500 mt-1">โดย: ${escapeHTML(submission.submitter_fullname)} (${new Date(submission.timestamp).toLocaleString('th-TH', { timeStyle: 'short' })} น.)</p>` : '';

        card.innerHTML = `<p class="font-semibold text-sm ${isSubmitted ? 'text-green-800' : 'text-red-800'}">${escapeHTML(dept)}</p>${statusLine}${detailsLine}`;
        summaryContainer.appendChild(card);
    });
}

function updateActiveStatusesView(filter, cache, chartElementId, unavailableContainerId, availableContainerId, unavailableTitleId, availableTitleId, chartColors, statusColors) {
    if (!cache) return;
    
    const { active_statuses, available_personnel } = cache;

    const unavailableContainer = document.getElementById(unavailableContainerId);
    const availableContainer = document.getElementById(availableContainerId);
    const chartContainer = document.getElementById(chartElementId).parentElement;
    const unavailableTitle = document.getElementById(unavailableTitleId);
    const availableTitle = document.getElementById(availableTitleId);

    let filteredUnavailable = active_statuses;
    let filteredAvailable = available_personnel;
    
    unavailableTitle.style.display = 'block';
    availableTitle.style.display = 'block';
    unavailableContainer.style.display = 'block';
    availableContainer.style.display = 'block';

    if (filter === 'ว่าง') {
        filteredUnavailable = [];
        unavailableContainer.style.display = 'none';
        unavailableTitle.style.display = 'none';
    } else if (filter !== 'ทั้งหมด') {
        filteredUnavailable = active_statuses.filter(s => s.status === filter);
        filteredAvailable = [];
        availableContainer.style.display = 'none';
        availableTitle.style.display = 'none';
    }

    // Chart Logic
    chartContainer.innerHTML = `<canvas id="${chartElementId}"></canvas>`;
    const ctx = document.getElementById(chartElementId).getContext('2d');
    if (window[chartElementId]) window[chartElementId].destroy();
    
    const status_counts = filteredUnavailable.reduce((acc, s) => { acc[s.status] = (acc[s.status] || 0) + 1; return acc; }, {});
    let chartLabels = [];
    let chartData = [];
    if (filter === 'ทั้งหมด' || filter === 'ว่าง') { chartLabels.push('ว่าง'); chartData.push(available_personnel.length); }
    chartLabels.push(...Object.keys(status_counts));
    chartData.push(...Object.values(status_counts));
    const dynamicChartColors = chartLabels.map(label => chartColors[label] || '#CCCCCC');

    window[chartElementId] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: chartLabels,
            datasets: [{ data: chartData, backgroundColor: dynamicChartColors, borderColor: '#FFFFFF', borderWidth: 2 }]
        },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '70%',
            plugins: {
                legend: { position: 'right', labels: { font: { family: "'Kanit', sans-serif", size: 14 }, boxWidth: 20 }},
                title: { display: false },
                datalabels: { formatter: (value) => value > 0 ? value : '', color: '#fff', font: { family: "'Kanit', sans-serif", weight: 'bold', size: 14 }}
            }
        }
    });

    // Table Logic
    const renderTable = (container, data, columns, isUnavailable) => {
        container.innerHTML = '';
        if (!data || data.length === 0) {
            container.innerHTML = `<div class="text-center p-4 text-gray-500">ไม่พบข้อมูล</div>`; return;
        }
        const headers = columns.map(col => `<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">${col}</th>`).join('');
        const rows = data.map((p, index) => {
            const bgColorClass = isUnavailable ? (statusColors[p.status] || '') : 'bg-green-50/50';
            const detailsHtml = isUnavailable ? `<td class="px-4 py-2">${escapeHTML(p.status)}</td><td class="px-4 py-2">${escapeHTML(p.details)}</td><td class="px-4 py-2">${formatThaiDateRangeArabic(p.start_date, p.end_date)}</td>` : '';
            return `<tr class="${bgColorClass}">
                <td class="px-4 py-2">${index + 1}</td>
                <td class="px-4 py-2">${escapeHTML(p.rank)} ${escapeHTML(p.first_name)} ${escapeHTML(p.last_name)}</td>
                <td class="px-4 py-2">${escapeHTML(p.department)}</td>
                ${detailsHtml}
            </tr>`;
        }).join('');
        container.innerHTML = `<table class="min-w-full bg-white text-sm"><thead class="bg-gray-50"><tr>${headers}</tr></thead><tbody class="bg-white divide-y divide-gray-200">${rows}</tbody></table>`;
    };
    
    if(unavailableContainer.style.display !== 'none') renderTable(unavailableContainer, filteredUnavailable, ['ลำดับ', 'ชื่อ-สกุล', 'แผนก', 'สถานะ', 'รายละเอียด', 'ช่วงวันที่'], true);
    if(availableContainer.style.display !== 'none') renderTable(availableContainer, filteredAvailable, ['ลำดับ', 'ชื่อ-สกุล', 'แผนก'], false);
}


function renderActiveStatuses(res) {
    fullDailyPersistentStatusDataCache = res; // Cache the data
    document.getElementById('status-title').textContent = `สถานะกำลังพลภาพรวม (ระยะยาว)`;

    const filterContainer = document.getElementById('status-filter-container');
    filterContainer.innerHTML = '';
    const filters = ['ทั้งหมด', 'ว่าง', ...Object.keys(STATUS_COLORS)];
    
    filters.forEach(filter => {
        const button = document.createElement('button');
        button.textContent = filter;
        button.dataset.filter = filter;
        button.className = 'persistent-status-filter-btn px-3 py-1 text-sm font-medium rounded-full border transition-colors bg-white text-gray-700 border-gray-300';
        button.addEventListener('click', () => updateActiveStatusesView(filter, fullDailyPersistentStatusDataCache, 'status-chart-canvas', 'unavailable-container', 'available-container', 'unavailable-title', 'available-title', PERSISTENT_CHART_COLORS, STATUS_COLORS));
        filterContainer.appendChild(button);
    });
    
    updateActiveStatusesView('ทั้งหมด', fullDailyPersistentStatusDataCache, 'status-chart-canvas', 'unavailable-container', 'available-container', 'unavailable-title', 'available-title', PERSISTENT_CHART_COLORS, STATUS_COLORS);
}



// --- Event Handlers ---
function handleReviewStatus() {
    // ... (omitted for brevity, same as previous version)
}

async function handleSubmitStatusReport() {
    // ... (omitted for brevity, same as previous version)
}

async function handleExportDailyReport() {
    // ... (omitted for brevity, same as previous version)
}


// --- Data Loading and Tab Switching ---
async function loadDataForPane(paneId) {
    let payload = {};
    const actions = {
        'pane-dashboard-daily': { action: 'get_daily_dashboard_summary', renderer: renderDailyDashboard },
        'pane-status-daily': { action: 'get_all_persistent_statuses', renderer: renderActiveStatuses },
        'pane-submit-status-daily': { action: 'get_personnel_for_daily_report', renderer: renderDailySubmissionForm },
        'pane-history-daily': { action: 'get_daily_submission_history', renderer: renderDailyHistory },
        'pane-summary-daily': { action: 'get_daily_summary_report', renderer: renderDailySummary },
    };

    const paneConfig = actions[paneId];
    if (!paneConfig) return;

    try {
        const res = await sendRequest(paneConfig.action, payload);
        if (res && res.status === 'success') {
            if (paneConfig.renderer) {
                paneConfig.renderer(res);
            }
        } else if (res && res.message) {
            showMessage(res.message, false);
        }
    } catch (error) {
        showMessage(error.message, false);
    }
}

function switchTab(tabId) {
    const clickedTab = document.getElementById(tabId);
    if (!clickedTab) return;
    const paneId = tabId.replace('tab-', 'pane-');

    if (clickedTab.classList.contains('active')) {
        loadDataForPane(paneId);
        return; 
    }

    tabs.forEach(tab => {
        const currentPaneId = tab.id.replace('tab-', 'pane-');
        const pane = document.getElementById(currentPaneId);
        if(!pane) return;

        const isActive = (tab.id === tabId);
        tab.classList.toggle('active', isActive);
        pane.classList.toggle('hidden', !isActive);
    });
    
    loadDataForPane(paneId);
}

