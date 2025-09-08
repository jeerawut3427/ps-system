// daily.js - Main script for the daily reporting system

// --- Imports ---
import { sendRequest } from './api.js';
import * as ui from './ui.js'; 
import { escapeHTML, formatThaiDateRangeArabic, exportSingleReportToExcel } from './utils.js';

// --- Global State ---
window.currentUser = null;
let currentDepartment = ''; // To store the department being reported
let currentReportDate = ''; // To store the target date for the report
let allDailyHistoryData = {}; // To cache history data
let allArchivedDailyData = {}; // To cache archived daily data
let currentDailyReports = []; // To store reports for archiving
window.editingDailyReportData = null; // To hold data for editing

// --- DOM References ---
let welcomeMessage, logoutBtn, backToSelectionBtn, appContainer, tabs, panes;
let dailyHistoryYearSelect, dailyHistoryMonthSelect, showDailyHistoryBtn, dailyHistoryContainer;
let dailySubmissionContent, reviewReportSectionDaily, reviewDailyStatusBtn, backToFormBtnDaily, confirmSubmitDailyBtn;
let bulkStatusButtonsDaily;
let dailyReportContainer, dailyArchiveContainer, exportDailyArchiveBtn;
let dailyArchiveYearSelect, dailyArchiveMonthSelect, showDailyArchiveBtn;
let archiveConfirmModal, cancelArchiveBtn, confirmArchiveBtn;


// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    assignDomElements();
    try {
        window.currentUser = JSON.parse(localStorage.getItem('currentUser'));
    } catch (e) {
        window.currentUser = null;
    }

    if (!window.currentUser) {
        window.location.href = '/login.html';
        return;
    }
    
    initializePage();
});

function assignDomElements() {
    appContainer = document.getElementById('app-container');
    welcomeMessage = document.getElementById('welcome-message');
    logoutBtn = document.getElementById('logout-btn');
    backToSelectionBtn = document.getElementById('back-to-selection-btn');
    tabs = document.querySelectorAll('.tab-button');
    panes = document.querySelectorAll('.tab-pane');
    
    dailyHistoryYearSelect = document.getElementById('daily-history-year-select');
    dailyHistoryMonthSelect = document.getElementById('daily-history-month-select');
    showDailyHistoryBtn = document.getElementById('show-daily-history-btn');
    dailyHistoryContainer = document.getElementById('daily-history-container');
    
    dailySubmissionContent = document.getElementById('daily-submission-content');
    reviewReportSectionDaily = document.getElementById('review-report-section-daily');
    reviewDailyStatusBtn = document.getElementById('review-daily-status-btn');
    backToFormBtnDaily = document.getElementById('back-to-form-btn-daily');
    confirmSubmitDailyBtn = document.getElementById('confirm-submit-daily-btn');
    bulkStatusButtonsDaily = document.getElementById('bulk-status-buttons-daily');

    // New elements for report and archive
    dailyReportContainer = document.getElementById('daily-report-container');
    dailyArchiveContainer = document.getElementById('daily-archive-container');
    exportDailyArchiveBtn = document.getElementById('export-daily-archive-btn');
    dailyArchiveYearSelect = document.getElementById('daily-archive-year-select');
    dailyArchiveMonthSelect = document.getElementById('daily-archive-month-select');
    showDailyArchiveBtn = document.getElementById('show-daily-archive-btn');
    
    archiveConfirmModal = document.getElementById('archive-confirm-modal');
    cancelArchiveBtn = document.getElementById('cancel-archive-btn');
    confirmArchiveBtn = document.getElementById('confirm-archive-btn');
}

async function initializePage() {
    appContainer.classList.remove('hidden');
    welcomeMessage.textContent = `ล็อกอินในฐานะ: ${escapeHTML(currentUser.username)} (${escapeHTML(currentUser.role)})`;
    
    logoutBtn.addEventListener('click', () => {
        sendRequest('logout', {}).finally(() => {
            localStorage.removeItem('currentUser');
            window.location.href = '/login.html';
        });
    });
    backToSelectionBtn.addEventListener('click', () => {
        window.location.href = '/selection.html';
    });
    tabs.forEach(tab => tab.addEventListener('click', () => switchTab(tab.id)));

    if(reviewDailyStatusBtn) reviewDailyStatusBtn.addEventListener('click', handleReviewDailyStatus);
    if(backToFormBtnDaily) backToFormBtnDaily.addEventListener('click', () => {
        reviewReportSectionDaily.classList.add('hidden');
        dailySubmissionContent.classList.remove('hidden');
    });
    if(confirmSubmitDailyBtn) confirmSubmitDailyBtn.addEventListener('click', handleSubmitDailyReport);

    if(showDailyHistoryBtn) showDailyHistoryBtn.addEventListener('click', renderFilteredDailyHistory);
    if(dailyHistoryYearSelect) dailyHistoryYearSelect.addEventListener('change', populateDailyHistoryMonths);
    if(dailyHistoryContainer) dailyHistoryContainer.addEventListener('click', handleDailyHistoryEditClick);
    
    if(exportDailyArchiveBtn) exportDailyArchiveBtn.addEventListener('click', () => {
        if (!currentDailyReports || currentDailyReports.length === 0) {
            ui.showMessage('ไม่มีข้อมูลรายงานที่จะส่งออก', false);
            return;
        }
        archiveConfirmModal.classList.add('active');
    });
    if(cancelArchiveBtn) cancelArchiveBtn.addEventListener('click', () => archiveConfirmModal.classList.remove('active'));
    if(confirmArchiveBtn) confirmArchiveBtn.addEventListener('click', handleArchiveDailyReport);
    if(showDailyArchiveBtn) showDailyArchiveBtn.addEventListener('click', renderFilteredDailyArchives);
    if(dailyArchiveYearSelect) dailyArchiveYearSelect.addEventListener('change', populateDailyArchiveMonths);

    const is_admin = (currentUser.role === 'admin');
    document.getElementById('tab-daily-dashboard').classList.toggle('hidden', !is_admin);
    document.getElementById('tab-daily-report').classList.toggle('hidden', !is_admin);
    document.getElementById('tab-daily-archive').classList.toggle('hidden', !is_admin);
    
    if (is_admin) {
        await switchTab('tab-daily-dashboard');
    } else {
        await switchTab('tab-daily-submit');
    }
}


// --- Tab Switching and Data Loading ---
async function loadDataForPane(paneId, department = null) {
    let payload = {};
    // If a department is passed (e.g., from admin dropdown), use it
    if (department) {
        payload.department = department;
    } 
    // If editing, ensure we load the data for the correct department from the report
    else if (window.editingDailyReportData) {
        payload.department = window.editingDailyReportData.department;
    }

    if(dailySubmissionContent) dailySubmissionContent.classList.remove('hidden');
    if(reviewReportSectionDaily) reviewReportSectionDaily.classList.add('hidden');
    
    if (paneId === 'pane-daily-submit') {
        try {
            const res = await sendRequest('get_daily_personnel_for_submission', payload);
            if (res.status === 'success') {
                currentDepartment = res.department;
                currentReportDate = res.report_date;
                renderSubmissionForm(res);
            } else {
                ui.showMessage(res.message, false);
            }
        } catch (error) {
            ui.showMessage(error.message, false);
        }
    }
    if (paneId === 'pane-daily-dashboard') {
        try {
            const res = await sendRequest('get_daily_dashboard_summary', {});
            if (res.status === 'success') {
                renderDailyDashboard(res.summary);
            } else {
                ui.showMessage(res.message, false);
            }
        } catch (error) {
            ui.showMessage(error.message, false);
        }
    }
    if (paneId === 'pane-daily-history') {
        try {
            const res = await sendRequest('get_daily_submission_history', {});
            if (res.status === 'success') {
                allDailyHistoryData = res.history || {};
                populateDailyHistoryYears();
                dailyHistoryContainer.innerHTML = '<p class="text-center text-gray-500">กรุณาเลือกปีและเดือนเพื่อแสดงประวัติ</p>';
            }
        } catch (error) {
            ui.showMessage(error.message, false);
        }
    }
    if (paneId === 'pane-daily-report') {
        try {
            const res = await sendRequest('get_daily_final_report', {});
            if (res.status === 'success') {
                renderDailyFinalReport(res);
            }
        } catch(error) {
            ui.showMessage(error.message, false);
        }
    }
     if (paneId === 'pane-daily-archive') {
        try {
            const res = await sendRequest('get_archived_daily_reports', {});
            if (res.status === 'success') {
                allArchivedDailyData = res.archives || {};
                populateDailyArchiveYears();
                if(dailyArchiveContainer) dailyArchiveContainer.innerHTML = '<p class="text-center text-gray-500">กรุณาเลือกปีและเดือนเพื่อแสดงประวัติ</p>';
            }
        } catch (error) {
            ui.showMessage(error.message, false);
        }
    }
}

async function switchTab(tabId) {
    for (const tab of tabs) {
        const paneId = tab.id.replace('tab-', 'pane-');
        const pane = document.getElementById(paneId);
        if (!pane) continue;

        if (tab.id === tabId) {
            tab.classList.add('active');
            tab.style.borderColor = '#0891b2';
            tab.style.color = '#0891b2';
            pane.classList.remove('hidden');
            await loadDataForPane(paneId);
        } else {
            tab.classList.remove('active');
            tab.style.borderColor = 'transparent';
            tab.style.color = '';
            pane.classList.add('hidden');
        }
    }
}

// --- Event Handlers ---
async function handleDailyHistoryEditClick(e) {
    if (!e.target || !e.target.classList.contains('edit-daily-history-btn')) return;
    
    const reportId = e.target.dataset.reportId;
    if (!reportId) return;

    try {
        const res = await sendRequest('get_daily_report_for_editing', { id: reportId });
        if (res.status === 'success' && res.report) {
            window.editingDailyReportData = res.report;
            if (currentUser.role === 'admin') {
                // We don't need to set the dropdown here because loadDataForPane will handle it
            }
            switchTab('tab-daily-submit');
        } else {
            ui.showMessage(res.message || 'ไม่สามารถดึงข้อมูลรายงานมาแก้ไขได้', false);
        }
    } catch (error) {
        ui.showMessage(error.message, false);
    }
}

function handleReviewDailyStatus() {
    const categories = {
        officer: { title: 'นายทหารสัญญาบัตร', reviewArea: 'review-list-area-officer', container: 'submission-list-officer' },
        nco: { title: 'นายทหารประทวน', reviewArea: 'review-list-area-nco', container: 'submission-list-nco' },
        civilian: { title: 'พลเรือนและพนักงานราชการ', reviewArea: 'review-list-area-civilian', container: 'submission-list-civilian' }
    };
    let totalLeave = 0;

    for (const key in categories) {
        const category = categories[key];
        const containerEl = document.getElementById(category.container);
        const reviewAreaEl = document.getElementById(category.reviewArea);
        const rows = containerEl.querySelectorAll('tbody > tr');
        const leaveItems = [];

        rows.forEach(row => {
            const status = row.querySelector('.status-select').value;
            if (status !== 'ไม่มี') {
                leaveItems.push({
                    name: row.querySelector('td:first-child').textContent,
                    status: status,
                    details: row.querySelector('.details-input').value,
                    startDate: row.querySelector('.start-date-input').value,
                    endDate: row.querySelector('.end-date-input').value,
                });
            }
        });

        totalLeave += leaveItems.length;

        if (leaveItems.length > 0) {
            let tableHTML = `<h3 class="text-md font-semibold text-gray-700 mb-2">${category.title}</h3>
            <table class="min-w-full bg-white text-sm mb-4">
                <thead class="bg-gray-100">
                    <tr>
                        <th class="px-2 py-2 text-left font-medium text-gray-600">ยศ-ชื่อ-สกุล</th>
                        <th class="px-2 py-2 text-left font-medium text-gray-600">สถานะ</th>
                        <th class="px-2 py-2 text-left font-medium text-gray-600">รายละเอียด</th>
                        <th class="px-2 py-2 text-left font-medium text-gray-600">ช่วงวันที่</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-200">
                    ${leaveItems.map(item => `
                        <tr>
                            <td class="px-2 py-2">${escapeHTML(item.name)}</td>
                            <td class="px-2 py-2">${escapeHTML(item.status)}</td>
                            <td class="px-2 py-2">${escapeHTML(item.details)}</td>
                            <td class="px-2 py-2">${formatThaiDateRangeArabic(item.startDate, item.endDate)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>`;
            reviewAreaEl.innerHTML = tableHTML;
        } else {
            reviewAreaEl.innerHTML = '';
        }
    }

    if (totalLeave === 0) {
        document.getElementById('review-list-area-officer').innerHTML = '<p class="text-center text-gray-600 bg-green-50 p-4 rounded-lg">กำลังพลว่างทั้งหมด (ไม่มีภารกิจ)</p>';
    }

    dailySubmissionContent.classList.add('hidden');
    reviewReportSectionDaily.classList.remove('hidden');
}

async function handleSubmitDailyReport() {
    confirmSubmitDailyBtn.disabled = true;
    confirmSubmitDailyBtn.textContent = 'กำลังบันทึก...';

    const categories = ['officer', 'nco', 'civilian'];
    const reportData = {};
    const summaryData = {};

    categories.forEach(key => {
        const containerEl = document.getElementById(`submission-list-${key}`);
        const rows = containerEl.querySelectorAll('tbody > tr');
        
        const total = rows.length;
        let available = 0;
        const missionItems = [];

        rows.forEach(row => {
            const status = row.querySelector('.status-select').value;
            if (status === 'ไม่มี') {
                available++;
            } else {
                missionItems.push({
                    personnel_id: row.dataset.id,
                    status: status,
                    details: row.querySelector('.details-input').value,
                    start_date: row.querySelector('.start-date-input').value,
                    end_date: row.querySelector('.end-date-input').value
                });
            }
        });
        
        reportData[key] = missionItems;
        summaryData[key] = { total, available, mission: total - available };
    });
    
    const payload = {
        data: {
            department: currentDepartment,
            report_date: currentReportDate,
            report_data: reportData,
            summary_data: summaryData
        }
    };

    try {
        const res = await sendRequest('submit_daily_report', payload);
        ui.showMessage(res.message, res.status === 'success');
        if (res.status === 'success') {
            reviewReportSectionDaily.classList.add('hidden');
            dailySubmissionContent.classList.remove('hidden');
            if (currentUser.role === 'admin') {
                switchTab('tab-daily-dashboard');
            } else {
                 loadDataForPane('pane-daily-submit');
            }
        }
    } catch(error) {
        ui.showMessage(error.message, false);
    } finally {
        confirmSubmitDailyBtn.disabled = false;
        confirmSubmitDailyBtn.textContent = 'ยืนยันและส่งยอด';
    }
}

async function handleArchiveDailyReport() {
    archiveConfirmModal.classList.remove('active');
    try {
        const response = await sendRequest('archive_daily_reports', { reports: currentDailyReports });
        ui.showMessage(response.message, response.status === 'success');
        if (response.status === 'success') {
            loadDataForPane('pane-daily-report');
        }
    } catch(error) {
        ui.showMessage(error.message, false);
    }
}


// --- Rendering and UI Update Functions ---
function formatThaiDate(isoDateString) {
    const date = new Date(isoDateString);
    const userTimezoneOffset = date.getTimezoneOffset() * 60000;
    const adjustedDate = new Date(date.getTime() + userTimezoneOffset);
    return adjustedDate.toLocaleDateString('th-TH', { dateStyle: 'full' });
}

function renderDailyDashboard(summary) {
    const container = document.getElementById('daily-dashboard-container');
    const dateEl = document.getElementById('daily-dashboard-date');
    const titleEl = document.querySelector('#pane-daily-dashboard h2');
    if (!container || !dateEl || !titleEl) return;
    
    titleEl.textContent = 'สรุปภาพรวมการส่งยอดประจำวัน';
    dateEl.textContent = `ข้อมูลสำหรับ: ${formatThaiDate(summary.report_date)}`;
    container.innerHTML = '';

    const { all_departments, submitted_info } = summary;

    if (!all_departments || all_departments.length === 0) {
        container.innerHTML = '<p class="text-gray-500 col-span-full">ไม่พบข้อมูลแผนกในระบบ</p>';
        return;
    }

    all_departments.forEach(dept => {
        const submission = submitted_info[dept];
        const isSubmitted = !!submission;
        const card = document.createElement('div');
        card.className = `p-4 rounded-lg border shadow-sm ${isSubmitted ? 'bg-green-50 border-green-300' : 'bg-red-50 border-red-300'}`;

        let summaryHtml = '';
        if (isSubmitted) {
            const { officer, nco, civilian } = submission.summary;
            summaryHtml = `
                <div class="mt-2 text-xs text-gray-600 space-y-1">
                    <p><b>สัญญาบัตร:</b> ยอด ${officer.total} ว่าง ${officer.available} ภารกิจ ${officer.mission}</p>
                    <p><b>ประทวน:</b> ยอด ${nco.total} ว่าง ${nco.available} ภารกิจ ${nco.mission}</p>
                    <p><b>พลเรือน:</b> ยอด ${civilian.total} ว่าง ${civilian.available} ภารกิจ ${civilian.mission}</p>
                </div>
            `;
        }

        let statusLine = isSubmitted ? `<p class="text-xs text-green-700">ส่งยอดแล้ว</p>` : `<p class="text-xs text-red-700">ยังไม่ส่งยอด</p>`;
        let detailsLine = isSubmitted ? `<p class="text-xs text-gray-500 mt-1">โดย: ${escapeHTML(submission.submitter_fullname)} (${new Date(submission.timestamp).toLocaleTimeString('th-TH')})</p>` : '';

        card.innerHTML = `<p class="font-semibold text-sm ${isSubmitted ? 'text-green-800' : 'text-red-800'}">${escapeHTML(dept)}</p>${statusLine}${summaryHtml}${detailsLine}`;
        container.appendChild(card);
    });
}

function updateCategorySummary(categoryKey) {
    const containerEl = document.getElementById(`submission-list-${categoryKey}`);
    const summaryEl = document.getElementById(`summary-${categoryKey}`);
    if (!containerEl || !summaryEl) return;

    const rows = containerEl.querySelectorAll('tbody > tr');
    const total = rows.length;
    let available = 0;

    rows.forEach(row => {
        const statusSelect = row.querySelector('.status-select');
        if (statusSelect.value === 'ไม่มี') {
            available++;
            row.classList.remove('row-selected');
        } else {
            row.classList.add('row-selected');
        }
    });
    const mission = total - available;
    summaryEl.textContent = `(ยอดทั้งหมด ${total} / ว่าง ${available} / ติดภารกิจ ${mission})`;
}

function renderSubmissionForm(res) {
    const { personnel, report_date, all_departments, submission_status } = res;

    const submissionInfoArea = document.getElementById('submission-info-area-daily');
    const submissionContent = document.getElementById('daily-submission-content');
    const adminSelectorContainer = document.getElementById('admin-dept-selector-container-daily');
    
    // Logic for showing/hiding form based on submission status
    if (submission_status) {
        const submittedTime = new Date(submission_status.timestamp).toLocaleString('th-TH', { dateStyle: 'full', timeStyle: 'short' });
        let message = `คุณได้ส่งยอดสำหรับวันที่ ${formatThaiDate(report_date)} ไปแล้วเมื่อ ${submittedTime} น.`;
        if (currentUser.role === 'admin') {
            message = `แผนกนี้ได้ส่งยอดสำหรับวันที่ ${formatThaiDate(report_date)} ไปแล้วเมื่อ ${submittedTime} น. 
                       <button id="go-to-history-btn" class="ml-2 text-sm text-blue-600 underline">คลิกที่นี่เพื่อแก้ไข</button>`;
        }
        submissionInfoArea.innerHTML = message;
        submissionInfoArea.classList.remove('hidden');
        submissionContent.classList.add('hidden');

        if (document.getElementById('go-to-history-btn')) {
            document.getElementById('go-to-history-btn').addEventListener('click', () => switchTab('tab-daily-history'));
        }
        // For admins, we still show the department selector
        if (currentUser.role !== 'admin') {
            adminSelectorContainer.classList.add('hidden');
        }
    } else {
        submissionInfoArea.classList.add('hidden');
        submissionContent.classList.remove('hidden');
        adminSelectorContainer.classList.remove('hidden');
    }

    // Render Admin Department Selector
    adminSelectorContainer.innerHTML = '';
    if (currentUser.role === 'admin' && all_departments) {
        // If editing, make sure the dropdown shows the correct department
        const departmentToSelect = window.editingDailyReportData ? window.editingDailyReportData.department : currentDepartment;
        let selectorHTML = `<label for="admin-dept-selector-daily" class="block text-sm font-medium text-gray-700 mb-1">เลือกแผนก</label>
            <select id="admin-dept-selector-daily" class="w-full md:w-1/3 border rounded px-2 py-2 bg-white shadow-sm">
            ${all_departments.map(dept => `<option value="${dept}" ${dept === departmentToSelect ? 'selected' : ''}>${dept}</option>`).join('')}
            </select>`;
        adminSelectorContainer.innerHTML = selectorHTML;
        document.getElementById('admin-dept-selector-daily').addEventListener('change', (e) => {
            loadDataForPane('pane-daily-submit', e.target.value);
        });
    }

    // Render bulk clear button
    const bulkButtonContainer = document.getElementById('bulk-status-buttons-daily');
    bulkButtonContainer.innerHTML = `<button id="clear-daily-form-btn" class="bg-gray-400 hover:bg-gray-500 text-white font-bold py-1 px-3 text-sm rounded-lg">ล้างค่า ทั้งหมด</button>`;
    document.getElementById('clear-daily-form-btn').addEventListener('click', () => {
         document.querySelectorAll('#pane-daily-submit tbody > tr').forEach(row => {
            const statusSelect = row.querySelector('.status-select');
            if (statusSelect) {
                statusSelect.value = 'ไม่มี';
                statusSelect.dispatchEvent(new Event('change'));
            }
            row.querySelector('.details-input').value = '';
            const startDateInput = row.querySelector('.start-date-input');
            if (startDateInput && startDateInput._flatpickr) startDateInput._flatpickr.clear();
            const endDateInput = row.querySelector('.end-date-input');
            if (endDateInput && endDateInput._flatpickr) endDateInput._flatpickr.clear();
         });
    });

    const dateEl = document.getElementById('daily-submit-date');
    if (dateEl) dateEl.textContent = `สำหรับวันที่: ${formatThaiDate(report_date)}`;
    
    const categories = {
        officer: { data: personnel.officer, container: 'submission-list-officer' },
        nco: { data: personnel.nco, container: 'submission-list-nco' },
        civilian: { data: personnel.civilian, container: 'submission-list-civilian' }
    };

    const flatpickrConfig = {
        locale: ui.thai_locale,
        altInput: true,
        altFormat: "j F Y",
        dateFormat: "Y-m-d",
        allowInput: true
    };

    for (const key in categories) {
        const { data, container } = categories[key];
        const containerEl = document.getElementById(container);
       
        if (!containerEl) continue;

        if (!data || data.length === 0) {
            containerEl.innerHTML = '<p class="text-gray-500 p-4">ไม่พบข้อมูลกำลังพลในประเภทนี้</p>';
            updateCategorySummary(key);
            continue;
        }

        let tableHTML = `<table class="min-w-full bg-white text-sm">
            <thead class="bg-gray-100">
                <tr>
                    <th class="px-2 py-2 text-left font-medium text-gray-600 w-[30%]">ยศ-ชื่อ-สกุล</th>
                    <th class="px-2 py-2 text-left font-medium text-gray-600 w-[15%]">สถานะ</th>
                    <th class="px-2 py-2 text-left font-medium text-gray-600 w-[25%]">รายละเอียด/หมายเหตุ</th>
                    <th class="px-2 py-2 text-left font-medium text-gray-600 w-[15%]">วันเริ่มต้น</th>
                    <th class="px-2 py-2 text-left font-medium text-gray-600 w-[15%]">วันสิ้นสุด</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">`;

        data.forEach(p => {
            const fullName = `${escapeHTML(p.rank)} ${escapeHTML(p.first_name)} ${escapeHTML(p.last_name)}`;
            tableHTML += `<tr data-id="${escapeHTML(p.id)}">
                <td class="px-2 py-2 font-semibold">${fullName}</td>
                <td class="px-2 py-2">
                    <select class="status-select w-full border rounded px-2 py-1 bg-white">
                        <option value="ไม่มี">ไม่มี</option>
                        <option value="ราชการ">ราชการ</option>
                        <option value="คุมงาน">คุมงาน</option>
                        <option value="ศึกษา">ศึกษา</option>
                        <option value="ลาพักผ่อน">ลาพักผ่อน</option>
                        <option value="ลากิจ">ลากิจ</option>
                        <option value="ลาป่วย">ลาป่วย</option>
                    </select>
                </td>
                <td class="px-2 py-2"><input type="text" class="details-input w-full border rounded px-2 py-1" placeholder="รายละเอียด (ถ้ามี)..."></td>
                <td class="px-2 py-2"><input type="text" class="start-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
                <td class="px-2 py-2"><input type="text" class="end-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
            </tr>`;
        });
        
        tableHTML += '</tbody></table>';
        containerEl.innerHTML = tableHTML;
        
        data.forEach(p => {
            const row = containerEl.querySelector(`tr[data-id="${p.id}"]`);
            if (row) {
                const statusSelect = row.querySelector('.status-select');
                statusSelect.value = p.status || 'ไม่มี';
                row.querySelector('.details-input').value = p.details || '';
                
                const startDatePicker = flatpickr(row.querySelector('.start-date-input'), flatpickrConfig);
                const endDatePicker = flatpickr(row.querySelector('.end-date-input'), flatpickrConfig);
                
                if (p.start_date) startDatePicker.setDate(p.start_date);
                if (p.end_date) endDatePicker.setDate(p.end_date);

                statusSelect.addEventListener('change', () => updateCategorySummary(key));
            }
        });
        updateCategorySummary(key);
    }
    
    // Pre-fill form if editing
    if (window.editingDailyReportData) {
        const categories = ['officer', 'nco', 'civilian'];
        categories.forEach(key => {
            const items = window.editingDailyReportData.report_data[key];
            if (items && items.length > 0) {
                const itemMap = items.reduce((map, item) => {
                    map[item.personnel_id] = item;
                    return map;
                }, {});

                const containerEl = document.getElementById(`submission-list-${key}`);
                containerEl.querySelectorAll('tbody > tr').forEach(row => {
                    const personId = row.dataset.id;
                    if (itemMap[personId]) {
                        const savedItem = itemMap[personId];
                        row.querySelector('.status-select').value = savedItem.status;
                        row.querySelector('.details-input').value = savedItem.details;
                        const startDatePicker = row.querySelector('.start-date-input')._flatpickr;
                        if (startDatePicker) startDatePicker.setDate(savedItem.start_date);
                        const endDatePicker = row.querySelector('.end-date-input')._flatpickr;
                        if (endDatePicker) endDatePicker.setDate(savedItem.end_date);
                    }
                });
            }
        });
        window.editingDailyReportData = null; // Clear after use
    }
    
    reviewReportSectionDaily.classList.add('hidden');
}

// --- Daily Report and Archive Rendering ---
function renderDailyFinalReport(res) {
    const { reports, report_date, all_departments, submitted_departments } = res;
    currentDailyReports = reports;

    const titleEl = document.querySelector('#pane-daily-report h2');
    titleEl.textContent = `ส่งรายงานประจำวัน (${formatThaiDate(report_date)})`;

    dailyReportContainer.innerHTML = '';
    
    const allSubmitted = all_departments.length > 0 && all_departments.every(dept => submitted_departments.includes(dept));

    if (exportDailyArchiveBtn) {
        exportDailyArchiveBtn.disabled = !allSubmitted;
        exportDailyArchiveBtn.classList.toggle('bg-gray-400', !allSubmitted);
        exportDailyArchiveBtn.classList.toggle('cursor-not-allowed', !allSubmitted);
        exportDailyArchiveBtn.classList.toggle('bg-blue-500', allSubmitted);
        exportDailyArchiveBtn.classList.toggle('hover:bg-blue-700', allSubmitted);
        exportDailyArchiveBtn.title = allSubmitted ? 'ส่งออกและเก็บรายงาน' : 'ต้องรอให้ทุกแผนกส่งรายงานก่อน';
    }

    if (!reports || reports.length === 0) {
        dailyReportContainer.innerHTML = '<p class="text-center text-gray-500">ยังไม่มีแผนกใดส่งรายงานสำหรับวันนี้</p>';
        return;
    }

    reports.forEach(report => {
        const reportWrapper = document.createElement('div');
        reportWrapper.className = 'p-4 border rounded-lg bg-gray-50 mb-4';
        const { officer, nco, civilian } = report.summary_data;
        
        let reportDetailsHTML = '';
        const categories = {'officer': 'สัญญาบัตร', 'nco': 'ประทวน', 'civilian': 'พลเรือน'};
        let allItems = [];

        for (const key in categories) {
            const items = report.report_data[key] || [];
             if(items.length > 0) {
                 items.forEach(item => {
                    allItems.push({
                        ...item,
                        category: categories[key],
                    });
                });
             }
        }
        
        if (allItems.length > 0) {
            reportDetailsHTML += '<div class="overflow-x-auto mt-3">';
            reportDetailsHTML += '<table class="min-w-full bg-white text-sm">';
            reportDetailsHTML += `<thead class="bg-gray-100"><tr>
                <th class="px-2 py-2 text-left font-medium text-gray-600">ประเภท</th>
                <th class="px-2 py-2 text-left font-medium text-gray-600">ยศ-ชื่อ-สกุล</th>
                <th class="px-2 py-2 text-left font-medium text-gray-600">สถานะ</th>
                <th class="px-2 py-2 text-left font-medium text-gray-600">รายละเอียด</th>
                <th class="px-2 py-2 text-left font-medium text-gray-600">ช่วงวันที่</th>
            </tr></thead>`;
            reportDetailsHTML += '<tbody class="divide-y divide-gray-200">';

            allItems.forEach(item => {
                 const personnelName = `${item.rank || ''} ${item.first_name || ''} ${item.last_name || ''}`.trim();
                 reportDetailsHTML += `<tr>
                    <td class="px-2 py-2">${escapeHTML(item.category)}</td>
                    <td class="px-2 py-2">${escapeHTML(personnelName)}</td>
                    <td class="px-2 py-2">${escapeHTML(item.status)}</td>
                    <td class="px-2 py-2">${escapeHTML(item.details)}</td>
                    <td class="px-2 py-2">${formatThaiDateRangeArabic(item.start_date, item.end_date)}</td>
                 </tr>`;
            });
            reportDetailsHTML += '</tbody></table></div>';
        }
        
        reportWrapper.innerHTML = `
            <div class="flex flex-wrap justify-between items-center mb-2 gap-2">
                <div>
                    <h3 class="text-lg font-semibold text-gray-800">${escapeHTML(report.department)}</h3>
                    <p class="text-sm text-gray-500">ส่งโดย: ${escapeHTML(report.rank)} ${escapeHTML(report.first_name)} ${escapeHTML(report.last_name)} (เวลา ${new Date(report.timestamp).toLocaleTimeString('th-TH')})</p>
                </div>
            </div>
            <div class="mt-2 text-sm text-gray-700 space-y-1 p-3 bg-white rounded border">
                <p><b>สัญญาบัตร:</b> ยอด ${officer.total}, ว่าง ${officer.available}, ภารกิจ ${officer.mission}</p>
                <p><b>ประทวน:</b> ยอด ${nco.total}, ว่าง ${nco.available}, ภารกิจ ${nco.mission}</p>
                <p><b>พลเรือน:</b> ยอด ${civilian.total}, ว่าง ${civilian.available}, ภารกิจ ${civilian.mission}</p>
            </div>
            ${reportDetailsHTML}
        `;
        dailyReportContainer.appendChild(reportWrapper);
    });
}

// --- Daily History Functions ---
function populateDailyHistoryYears() {
    dailyHistoryYearSelect.innerHTML = '<option value="">เลือกปี</option>';
    dailyHistoryMonthSelect.innerHTML = '<option value="">เลือกเดือน</option>';
    if (allDailyHistoryData && Object.keys(allDailyHistoryData).length > 0) {
        const sortedYears = Object.keys(allDailyHistoryData).sort((a, b) => b - a);
        sortedYears.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            dailyHistoryYearSelect.appendChild(option);
        });
    }
}

function populateDailyHistoryMonths() {
    const selectedYear = dailyHistoryYearSelect.value;
    dailyHistoryMonthSelect.innerHTML = '<option value="">เลือกเดือน</option>';
    if (selectedYear && allDailyHistoryData[selectedYear]) {
        const sortedMonths = Object.keys(allDailyHistoryData[selectedYear]).sort((a, b) => b - a);
        sortedMonths.forEach(month => {
            const option = document.createElement('option');
            option.value = month;
            option.textContent = new Date(2000, parseInt(month) - 1, 1).toLocaleString('th-TH', { month: 'long' });
            dailyHistoryMonthSelect.appendChild(option);
        });
    }
}

function renderFilteredDailyHistory() {
    const year = dailyHistoryYearSelect.value;
    const month = dailyHistoryMonthSelect.value;
    if (!year || !month) {
        ui.showMessage('กรุณาเลือกปีและเดือน', false);
        return;
    }
    const reportsForMonth = allDailyHistoryData[year] ? allDailyHistoryData[year][month] : [];
    
    dailyHistoryContainer.innerHTML = '';

    if (!reportsForMonth || reportsForMonth.length === 0) {
        dailyHistoryContainer.innerHTML = '<p class="text-center text-gray-500">ไม่พบประวัติการส่งรายงานสำหรับเดือนที่เลือก</p>';
        return;
    }

    reportsForMonth.forEach(report => {
        const reportWrapper = document.createElement('div');
        reportWrapper.className = 'p-4 border rounded-lg bg-gray-50 mb-4';
        
        const { officer, nco, civilian } = report.summary;
        let summaryHtml = `
            <div class="mt-2 text-sm text-gray-700 space-y-1 p-3 bg-white rounded">
                <p><b>สัญญาบัตร:</b> ยอดทั้งหมด ${officer.total} / ว่าง ${officer.available} / ติดภารกิจ ${officer.mission}</p>
                <p><b>ประทวน:</b> ยอดทั้งหมด ${nco.total} / ว่าง ${nco.available} / ติดภารกิจ ${nco.mission}</p>
                <p><b>พลเรือน:</b> ยอดทั้งหมด ${civilian.total} / ว่าง ${civilian.available} / ติดภารกิจ ${civilian.mission}</p>
            </div>`;

        let submittedByText = (currentUser.role === 'admin') ? `แผนก: ${escapeHTML(report.department)} | ` : '';
        submittedByText += `ส่งโดย: ${escapeHTML(report.submitted_by)}`;

        const editButtonHtml = `<button data-report-id="${report.id}" class="edit-daily-history-btn bg-yellow-500 hover:bg-yellow-600 text-white text-sm font-bold py-1 px-3 rounded-lg">แก้ไข</button>`;

        reportWrapper.innerHTML = `
            <div class="flex flex-wrap justify-between items-center mb-2 gap-2">
                <div>
                    <h4 class="text-lg font-semibold text-gray-800">รายงานสำหรับวันที่ ${formatThaiDate(report.report_date)}</h4>
                    <span class="text-sm text-gray-500">${submittedByText} (เวลา ${new Date(report.timestamp).toLocaleTimeString('th-TH')})</span>
                </div>
                ${editButtonHtml}
            </div>
            ${summaryHtml}`;
        dailyHistoryContainer.appendChild(reportWrapper);
    });
}

// --- Daily Archive Functions ---
function populateDailyArchiveYears() {
    dailyArchiveYearSelect.innerHTML = '<option value="">เลือกปี</option>';
    if (allArchivedDailyData && Object.keys(allArchivedDailyData).length > 0) {
        const sortedYears = Object.keys(allArchivedDailyData).sort((a, b) => b - a);
        sortedYears.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = parseInt(year) + 543;
            dailyArchiveYearSelect.appendChild(option);
        });
    }
}

function populateDailyArchiveMonths() {
    const selectedYear = dailyArchiveYearSelect.value;
    dailyArchiveMonthSelect.innerHTML = '<option value="">เลือกเดือน</option>';
    if (selectedYear && allArchivedDailyData[selectedYear]) {
        const sortedMonths = Object.keys(allArchivedDailyData[selectedYear]).sort((a, b) => b - a);
        sortedMonths.forEach(month => {
            const option = document.createElement('option');
            option.value = month;
            option.textContent = new Date(2000, parseInt(month) - 1, 1).toLocaleString('th-TH', { month: 'long' });
            dailyArchiveMonthSelect.appendChild(option);
        });
    }
}

function renderFilteredDailyArchives() {
    const year = dailyArchiveYearSelect.value;
    const month = dailyArchiveMonthSelect.value;
    if (!year || !month) {
        ui.showMessage('กรุณาเลือกปีและเดือน', false);
        return;
    }
    const reportsForMonth = allArchivedDailyData[year] ? allArchivedDailyData[year][month] : [];
    
    dailyArchiveContainer.innerHTML = '';

    if (!reportsForMonth || reportsForMonth.length === 0) {
        dailyArchiveContainer.innerHTML = '<p class="text-center text-gray-500">ไม่พบรายงานที่เก็บถาวรสำหรับเดือนที่เลือก</p>';
        return;
    }

    const reportsByDate = reportsForMonth.reduce((acc, report) => {
        const date = report.report_date;
        if(!acc[date]) acc[date] = [];
        acc[date].push(report);
        return acc;
    }, {});

    Object.keys(reportsByDate).sort((a,b) => new Date(b) - new Date(a)).forEach(date => {
        const dateCard = document.createElement('div');
        dateCard.className = 'mb-6 p-4 border rounded-lg bg-gray-50';
        
        let reportsHtml = '';
        reportsByDate[date].forEach(report => {
            const { officer, nco, civilian } = report.summary_data;
            reportsHtml += `
            <div class="mt-4 p-3 bg-white rounded border">
                 <p class="text-md font-semibold text-gray-800">${escapeHTML(report.department)}</p>
                 <p class="text-xs text-gray-500 mb-2">ส่งโดย: ${escapeHTML(report.submitted_by)}</p>
                 <div class="text-xs text-gray-700 space-y-1">
                    <p><b>สัญญาบัตร:</b> ยอด ${officer.total}, ว่าง ${officer.available}, ภารกิจ ${officer.mission}</p>
                    <p><b>ประทวน:</b> ยอด ${nco.total}, ว่าง ${nco.available}, ภารกิจ ${nco.mission}</p>
                    <p><b>พลเรือน:</b> ยอด ${civilian.total}, ว่าง ${civilian.available}, ภารกิจ ${civilian.mission}</p>
                 </div>
            </div>`;
        });
        
        dateCard.innerHTML = `
            <div class="flex justify-between items-center">
                <h3 class="text-lg font-semibold text-gray-800">รายงานวันที่ ${formatThaiDate(date)}</h3>
            </div>
            ${reportsHtml}
        `;
        dailyArchiveContainer.appendChild(dateCard);
    });
}
