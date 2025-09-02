// app_daily.js
// Main application file for the DAILY reporting system.

import { sendRequest } from './api.js';
import { escapeHTML, formatThaiDateArabic, formatThaiDateRangeArabic } from './utils.js';
import { showMessage, createEmptyState } from './ui.js';

// --- Global State and DOM References ---
let currentUser = null;
let fullDailyPersistentStatusDataCache = null; 

// --- Thai locale for Flatpickr ---
const thai_locale = {
    weekdays: { shorthand: ["อา", "จ", "อ", "พ", "พฤ", "ศ", "ส"] },
    months: { longhand: ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"] },
    firstDayOfWeek: 0,
    rangeSeparator: " ถึง ",
};

// --- Color Constants ---
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
let historyContainer, historyDeptSelectorContainer, historyDeptSelect;
let reportContainerDaily, exportExcelBtnDaily;

function assignDomElements() {
    appContainer = document.getElementById('app-container');
    messageArea = document.getElementById('message-area');
    welcomeMessage = document.getElementById('welcome-message');
    logoutBtn = document.getElementById('logout-btn');
    tabs = document.querySelectorAll('.tab-button');
    panes = document.querySelectorAll('.tab-pane');
    statusSubmissionListArea = document.getElementById('status-submission-list-area');
    submitStatusTitle = document.getElementById('submit-status-title');
    submissionFormSection = document.getElementById('submission-form-section');
    reviewReportSection = document.getElementById('review-report-section');
    reviewListArea = document.getElementById('review-list-area');
    backToFormBtn = document.getElementById('back-to-form-btn');
    confirmSubmitBtn = document.getElementById('confirm-submit-btn');
    reviewStatusBtn = document.getElementById('review-status-btn');
    historyContainer = document.getElementById('history-container');
    historyDeptSelectorContainer = document.getElementById('history-dept-selector-container');
    historyDeptSelect = document.getElementById('history-dept-select');
    reportContainerDaily = document.getElementById('report-container-daily');
    exportExcelBtnDaily = document.getElementById('export-excel-btn-daily');
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
        backToSelectionBtn.addEventListener('click', () => window.location.href = '/selection.html');
    }

    const is_admin = (userRole === 'admin');
    
    document.getElementById('tab-dashboard-daily')?.classList.toggle('hidden', !is_admin);
    document.getElementById('tab-status-daily')?.classList.toggle('hidden', !is_admin);
    document.getElementById('tab-report-daily')?.classList.toggle('hidden', !is_admin);

    if (is_admin) {
        switchTab('tab-dashboard-daily');
    } else {
        switchTab('tab-submit-status-daily');
    }
    
    logoutBtn.addEventListener('click', () => performLogout());

    ['mousemove', 'keydown', 'click'].forEach(event => window.addEventListener(event, resetInactivityTimer));
    resetInactivityTimer();

    tabs.forEach(tab => tab.addEventListener('click', () => switchTab(tab.id)));
    
    if (reviewStatusBtn) reviewStatusBtn.addEventListener('click', handleReviewStatus);
    if (backToFormBtn) backToFormBtn.addEventListener('click', () => {
        reviewReportSection.classList.add('hidden');
        submissionFormSection.classList.remove('hidden');
    });
    if (confirmSubmitBtn) confirmSubmitBtn.addEventListener('click', handleSubmitStatusReport);
    if (historyDeptSelect) historyDeptSelect.addEventListener('change', () => loadDataForPane('pane-history-daily'));
    if (exportExcelBtnDaily) exportExcelBtnDaily.addEventListener('click', handleExportDailyReport);
}

// --- UI Rendering ---
function renderDailyDashboard(res) {
    const summary = res.summary;
    if (!summary) return;
    
    document.getElementById('daily-dashboard-date').textContent = formatThaiDateArabic(summary.date);
    document.getElementById('daily-dashboard-total-personnel').textContent = summary.total_personnel || '0';
    
    const presentCount = summary.status_summary['มาปฏิบัติงาน'] || 0;
    const absentCount = summary.total_personnel - presentCount; // Calculate absent based on total
    
    document.getElementById('daily-dashboard-present').textContent = presentCount;
    document.getElementById('daily-dashboard-absent').textContent = absentCount;
    
    const deptStatusArea = document.getElementById('daily-dashboard-department-status');
    deptStatusArea.innerHTML = '';

    if (summary.all_departments?.length > 0) {
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
    const bulkButtonContainer = document.getElementById('bulk-status-buttons');

    if (!submissionFormSection || !submissionInfoArea || !statusSubmissionListArea || !submitStatusTitle || !adminSelectorContainer || !bulkButtonContainer) return;

    const displayFormForDept = (dept) => {
        const isSubmitted = submission_status && submission_status[dept];
        
        if (isSubmitted) {
            const submittedTime = new Date(isSubmitted.timestamp).toLocaleString('th-TH');
            submissionInfoArea.innerHTML = `แผนก ${escapeHTML(dept)} ได้ส่งยอดสำหรับวันพรุ่งนี้ไปแล้วเมื่อ ${submittedTime} น.`;
            submissionInfoArea.classList.remove('hidden');
            submissionFormSection.classList.add('hidden');
            bulkButtonContainer.classList.add('hidden');
        } else {
            submissionInfoArea.classList.add('hidden');
            submissionFormSection.classList.remove('hidden');
            bulkButtonContainer.classList.remove('hidden');
        }

        submitStatusTitle.textContent = `ส่งยอดกำลังพลประจำวัน แผนก ${escapeHTML(dept)}`;
        statusSubmissionListArea.innerHTML = '';
        
        const personnelInDept = personnel.filter(p => p.department === dept);

        if (personnelInDept.length === 0) {
            statusSubmissionListArea.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-gray-500">ไม่พบข้อมูลกำลังพลในแผนกนี้</td></tr>';
            return;
        }

        personnelInDept.forEach((p, index) => {
            const row = document.createElement('tr');
            row.dataset.personnelId = escapeHTML(p.id);
            row.dataset.personnelName = `${escapeHTML(p.rank)} ${escapeHTML(p.first_name)} ${escapeHTML(p.last_name)}`;
            row.innerHTML = `
                <td class="px-4 py-2">${index + 1}</td>
                <td class="px-4 py-2 font-semibold">${row.dataset.personnelName}</td>
                <td class="px-4 py-2"><select class="status-select w-full border rounded px-2 py-1 bg-white"></select></td>
                <td class="px-4 py-2"><input type="text" class="details-input w-full border rounded px-2 py-1" placeholder="รายละเอียด/สถานที่..."></td>
                <td class="px-4 py-2"><input type="text" class="start-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
                <td class="px-4 py-2"><input type="text" class="end-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
                <td class="px-4 py-2"><button type="button" class="add-status-btn bg-green-500 hover:bg-green-600 text-white font-bold py-1 px-2 rounded-full text-xs">+</button></td>
            `;
            
            const statusSelect = row.querySelector('.status-select');
            statusSelect.innerHTML = `<option value="มาปฏิบัติงาน">มาปฏิบัติงาน</option><option value="ราชการ">ราชการ</option><option value="คุมงาน">คุมงาน</option><option value="ศึกษา">ศึกษา</option><option value="ลากิจ">ลากิจ</option><option value="ลาพักผ่อน">ลาพักผ่อน</option>`;
            
            statusSubmissionListArea.appendChild(row);

            const flatpickrConfig = { locale: thai_locale, altInput: true, altFormat: "j F Y", dateFormat: "Y-m-d", allowInput: true };
            flatpickr(row.querySelector('.start-date-input'), flatpickrConfig);
            flatpickr(row.querySelector('.end-date-input'), flatpickrConfig);
        });
    };

    // Bulk actions
    bulkButtonContainer.innerHTML = '';
    const setAllStatus = (status) => {
        statusSubmissionListArea.querySelectorAll('tr').forEach(row => {
            const statusSelect = row.querySelector('.status-select');
            if (statusSelect) {
                statusSelect.value = status;
                // Clear other fields if status is 'มาปฏิบัติงาน'
                if (status === 'มาปฏิบัติงาน') {
                    row.querySelector('.details-input').value = '';
                    if (row.querySelector('.start-date-input')._flatpickr) row.querySelector('.start-date-input')._flatpickr.clear();
                    if (row.querySelector('.end-date-input')._flatpickr) row.querySelector('.end-date-input')._flatpickr.clear();
                }
            }
        });
    };
    const button = document.createElement('button');
    button.textContent = 'ตั้งค่าทั้งหมดเป็น "มาปฏิบัติงาน"';
    button.className = `text-white font-bold py-1 px-3 text-sm rounded-lg bg-gray-400 hover:bg-gray-500`;
    button.addEventListener('click', () => setAllStatus('มาปฏิบัติงาน'));
    bulkButtonContainer.appendChild(button);

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
        
        displayFormForDept(selector.value);

        selector.addEventListener('change', (e) => displayFormForDept(e.target.value));

    } else {
        adminSelectorContainer.classList.add('hidden');
        displayFormForDept(currentUser.department);
    }
}

function renderDailyHistory(res) {
    if (!historyContainer || !historyDeptSelectorContainer || !historyDeptSelect) return;
    historyContainer.innerHTML = '';
    const { history, all_departments } = res;

    if (currentUser.role === 'admin') {
        historyDeptSelectorContainer.classList.remove('hidden');
        const currentSelection = historyDeptSelect.value;
        historyDeptSelect.innerHTML = '<option value="">-- ทุกแผนก --</option>';
        all_departments.forEach(dept => {
            const option = document.createElement('option');
            option.value = dept;
            option.textContent = dept;
            if (dept === currentSelection) option.selected = true;
            historyDeptSelect.appendChild(option);
        });
    }

    const selectedDept = currentUser.role === 'admin' ? historyDeptSelect.value : currentUser.department;
    
    if (!history || Object.keys(history).length === 0) {
        historyContainer.innerHTML = createEmptyState('ยังไม่มีประวัติการส่งรายงาน');
        return;
    }

    const sortedDates = Object.keys(history).sort((a, b) => new Date(b) - new Date(a));
    let hasVisibleReports = false;

    sortedDates.forEach(date => {
        let reportsForDate = history[date];
        if (selectedDept) {
            reportsForDate = reportsForDate.filter(r => r.department === selectedDept);
        }
        if (reportsForDate.length === 0) return;

        hasVisibleReports = true;
        const dateCard = document.createElement('div');
        dateCard.className = 'mb-6 p-4 border rounded-lg bg-gray-50';
        
        let reportsHtml = reportsForDate.map(report => {
            const itemsHtml = report.items.map((item, index) => `
                <tr class="border-t">
                    <td class="py-2 pr-2 text-center">${index + 1}</td>
                    <td class="py-2 px-2">${escapeHTML(item.personnel_name)}</td>
                    <td class="py-2 px-2 ${item.status === 'มาปฏิบัติงาน' ? 'text-green-600' : 'text-blue-600'}">${escapeHTML(item.status)}</td>
                    <td class="py-2 px-2 text-gray-600">${escapeHTML(item.details) || '-'}</td>
                </tr>`).join('');

            return `<div class="mt-4">
                <div class="text-sm text-gray-500 mb-2">แผนก: <strong>${escapeHTML(report.department)}</strong> (ส่งเมื่อ: ${new Date(report.timestamp).toLocaleString('th-TH')})</div>
                <table class="min-w-full bg-white text-sm">
                    <thead><tr><th class="text-center font-medium text-gray-500 uppercase pb-1 w-[5%]">ลำดับ</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[40%]">ชื่อ-สกุล</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[20%]">สถานะ</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[35%]">หมายเหตุ</th></tr></thead>
                    <tbody>${itemsHtml}</tbody>
                </table>
            </div>`;
        }).join('');

        dateCard.innerHTML = `<h3 class="text-lg font-semibold text-gray-800">ประวัติการส่งของวันที่ ${formatThaiDateArabic(date)}</h3>${reportsHtml}`;
        historyContainer.appendChild(dateCard);
    });

    if (!hasVisibleReports) {
        historyContainer.innerHTML = createEmptyState('ไม่พบประวัติการส่งรายงานสำหรับแผนกที่เลือก');
    }
}

function renderDailyReports(res) {
    if(!reportContainerDaily) return;
    reportContainerDaily.innerHTML = '';
    const { reports, date } = res;
    
    document.getElementById('report-date-daily').textContent = formatThaiDateArabic(date);

    if (!reports || reports.length === 0) {
        reportContainerDaily.innerHTML = createEmptyState('ยังไม่มีแผนกใดส่งรายงานสำหรับวันพรุ่งนี้');
        return;
    }

    reports.forEach(report => {
        const reportWrapper = document.createElement('div');
        reportWrapper.className = 'p-4 border rounded-lg bg-gray-50 mb-4';
        const itemsHtml = report.items.map((item, index) => `<tr class="border-t"><td class="py-2 pr-2 text-center">${index + 1}</td><td class="py-2 px-2">${escapeHTML(item.personnel_name)}</td><td class="py-2 px-2 ${item.status === 'มาปฏิบัติงาน' ? 'text-green-600' : 'text-blue-600'}">${escapeHTML(item.status)}</td><td class="py-2 px-2 text-gray-600">${escapeHTML(item.details) || '-'}</td></tr>`).join('');
        reportWrapper.innerHTML = `
            <h3 class="text-lg font-semibold text-gray-700 mb-2">แผนก: ${escapeHTML(report.department)}</h3>
            <div class="overflow-x-auto">
                <table class="min-w-full bg-white text-sm">
                    <thead><tr><th class="text-center font-medium text-gray-500 uppercase pb-1 w-[5%]">ลำดับ</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[40%]">ชื่อ-สกุล</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[20%]">สถานะ</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[35%]">รายละเอียด</th></tr></thead>
                    <tbody>${itemsHtml}</tbody>
                </table>
            </div>`;
        reportContainerDaily.appendChild(reportWrapper);
    });
}


function renderActiveStatuses(res) {
    fullDailyPersistentStatusDataCache = res; 
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

function updateActiveStatusesView(filter, cache, chartElementId, unavailableContainerId, availableContainerId, unavailableTitleId, availableTitleId, chartColors, statusColors) {
    if (!cache) return;
    
    const { active_statuses, available_personnel } = cache;

    const unavailableContainer = document.getElementById(unavailableContainerId);
    const availableContainer = document.getElementById(availableContainerId);
    const chartContainer = document.getElementById(chartElementId).parentElement;
    const unavailableTitle = document.getElementById(unavailableTitleId);
    const availableTitle = document.getElementById(availableTitleId);

    let filteredUnavailable = active_statuses;
    
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
        availableContainer.style.display = 'none';
        availableTitle.style.display = 'none';
    }

    // Chart Logic
    chartContainer.innerHTML = `<canvas id="${chartElementId}"></canvas>`;
    const ctx = document.getElementById(chartElementId).getContext('2d');
    
    if (window[chartElementId] && typeof window[chartElementId].destroy === 'function') {
        window[chartElementId].destroy();
    }
    
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
    if(availableContainer.style.display !== 'none') renderTable(availableContainer, available_personnel, ['ลำดับ', 'ชื่อ-สกุล', 'แผนก'], false);
}

// --- Event Handlers ---
function handleReviewStatus() {
    // This logic is now identical to the weekly report, handling multiple statuses per person.
    const rows = statusSubmissionListArea.querySelectorAll('tr');
    const reviewItems = [];
    let hasError = false;

    rows.forEach(row => {
        const statusSelect = row.querySelector('.status-select');
        if (statusSelect && statusSelect.value !== 'มาปฏิบัติงาน') {
            const startDate = row.querySelector('.start-date-input').value;
            const endDate = row.querySelector('.end-date-input').value;
            if (!startDate || !endDate) {
                showMessage('กรุณากรอกวันที่เริ่มต้นและสิ้นสุดสำหรับรายการที่เลือก', false);
                hasError = true; return;
            }
            reviewItems.push({
                personnel_id: row.dataset.personnelId,
                personnel_name: row.dataset.personnelName,
                status: statusSelect.value,
                details: row.querySelector('.details-input').value,
                start_date: startDate,
                end_date: endDate
            });
        }
    });

    if (hasError) return;

    if (reviewItems.length === 0) {
        reviewListArea.innerHTML = `<tr><td colspan="4" class="text-center py-4 text-gray-500">ยืนยันการส่งยอด: กำลังพลมาปฏิบัติงานครบถ้วน</td></tr>`;
    } else {
        reviewListArea.innerHTML = reviewItems.map(item => `
            <tr>
                <td class="border-t px-4 py-2">${escapeHTML(item.personnel_name)}</td>
                <td class="border-t px-4 py-2">${escapeHTML(item.status)}</td>
                <td class="border-t px-4 py-2">${escapeHTML(item.details) || '-'}</td>
                <td class="border-t px-4 py-2">${formatThaiDateRangeArabic(item.start_date, item.end_date)}</td>
            </tr>`).join('');
    }

    submissionFormSection.classList.add('hidden');
    reviewReportSection.classList.remove('hidden');
}

async function handleSubmitStatusReport() {
    if (confirmSubmitBtn) {
        confirmSubmitBtn.disabled = true;
        confirmSubmitBtn.textContent = 'กำลังส่ง...';
    }
    
    const reportMap = new Map();
    statusSubmissionListArea.querySelectorAll('tr').forEach(row => {
        const id = row.dataset.personnelId;
        const name = row.dataset.personnelName;
        if (!id) return;

        if (!reportMap.has(id)) {
            reportMap.set(id, { personnel_id: id, personnel_name: name, items: [] });
        }
        
        const statusSelect = row.querySelector('.status-select');
        if (statusSelect.value !== 'มาปฏิบัติงาน') {
             reportMap.get(id).items.push({
                status: statusSelect.value, 
                details: row.querySelector('.details-input').value,
                start_date: row.querySelector('.start-date-input').value,
                end_date: row.querySelector('.end-date-input').value
            });
        }
    });

    const finalReportItems = [];
    for (const person of reportMap.values()) {
        if (person.items.length > 0) {
            finalReportItems.push(...person.items.map(item => ({...item, personnel_id: person.personnel_id, personnel_name: person.personnel_name })));
        } else {
            // Still include them as "มาปฏิบัติงาน" so the report is complete.
            finalReportItems.push({
                personnel_id: person.personnel_id,
                personnel_name: person.personnel_name,
                status: 'มาปฏิบัติงาน',
                details: '',
                start_date: '',
                end_date: ''
            });
        }
    }

    let reportDepartment = currentUser.department;
    if (currentUser.role === 'admin') {
        reportDepartment = document.getElementById('admin-dept-selector')?.value || currentUser.department;
    }

    try {
        const response = await sendRequest('submit_daily_status_report', { report: { items: finalReportItems, department: reportDepartment } });
        showMessage(response.message, response.status === 'success');
        if (response.status === 'success') {
            reviewReportSection.classList.add('hidden');
            loadDataForPane(currentUser.role === 'admin' ? 'tab-dashboard-daily' : 'pane-submit-status-daily');
        }
    } catch(error) {
        showMessage(error.message, false);
    } finally {
        if (confirmSubmitBtn) {
            confirmSubmitBtn.disabled = false;
            confirmSubmitBtn.textContent = 'ยืนยันและส่งยอด';
        }
    }
}

async function handleExportDailyReport() {
    showMessage("กำลังเตรียมข้อมูลสำหรับ Export...", true);
    const res = await sendRequest('get_full_daily_report_for_export', {});
    if (res.status === 'success' && res.reports?.length > 0) {
        // Needs a new utility function for daily report format
        // exportDailyReportToExcel(res.reports, `รายงานประจำวัน-${res.date}.xlsx`);
        showMessage("ฟังก์ชัน Export ยังไม่เปิดใช้งาน", false);
    } else {
        showMessage("ไม่พบข้อมูลรายงานประจำวันที่จะ Export", false);
    }
}


// --- Data Loading and Tab Switching ---
async function loadDataForPane(paneId) {
    let payload = {};
    const actions = {
        'pane-dashboard-daily': { action: 'get_daily_dashboard_summary', renderer: renderDailyDashboard },
        'pane-status-daily': { action: 'get_all_persistent_statuses', renderer: renderActiveStatuses },
        'pane-submit-status-daily': { action: 'get_personnel_for_daily_report', renderer: renderDailySubmissionForm },
        'pane-history-daily': { action: 'get_daily_submission_history', renderer: renderDailyHistory },
        'pane-report-daily': { action: 'get_daily_reports', renderer: renderDailyReports },
    };

    const paneConfig = actions[paneId];
    if (!paneConfig) return;

    if (paneId === 'pane-history-daily' && currentUser.role === 'admin') {
        payload.department = historyDeptSelect.value;
    }

    try {
        const res = await sendRequest(paneConfig.action, payload);
        if (res?.status === 'success') {
            paneConfig.renderer?.(res);
        } else {
            showMessage(res?.message || 'เกิดข้อผิดพลาดในการโหลดข้อมูล', false);
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

