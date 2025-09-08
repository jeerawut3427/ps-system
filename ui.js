// ui.js
// Contains all functions related to updating and rendering the user interface.

import { escapeHTML, formatThaiDateArabic, formatThaiDateRangeArabic } from './utils.js';

const ITEMS_PER_PAGE = 15;

// --- Thai locale settings for Flatpickr ---
export const thai_locale = {
    weekdays: {
        shorthand: ["อา", "จ", "อ", "พ", "พฤ", "ศ", "ส"],
        longhand: ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"],
    },
    months: {
        shorthand: ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."],
        longhand: ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"],
    },
    firstDayOfWeek: 0,
    rangeSeparator: " ถึง ",
    scrollTitle: "เลื่อนเพื่อเปลี่ยน",
    toggleTitle: "คลิกเพื่อสลับ",
    ordinal: function () { return ""; },
    era: "พ.ศ.",
};

// --- Color settings for statuses ---
const STATUS_COLORS = {
    'ราชการ': 'bg-blue-50',
    'คุมงาน': 'bg-indigo-50',
    'ศึกษา': 'bg-purple-50',
    'ลากิจ': 'bg-red-50',
    'ลาพักผ่อน': 'bg-green-50',
    'ลาป่วย': 'bg-yellow-50',
};

// --- Color settings for the chart ---
const CHART_STATUS_COLORS = {
    'ว่าง': '#4CAF50',
    'ราชการ': '#3B82F6',
    'คุมงาน': '#6366F1',
    'ศึกษา': '#8B5CF6',
    'ลากิจ': '#EF4444',
    'ลาพักผ่อน': '#10B981',
};


// --- Function to create an empty state message ---
function createEmptyState(message) {
    return `
        <div class="text-center py-10 px-4">
            <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2z" />
            </svg>
            <h3 class="mt-2 text-sm font-medium text-gray-900">ไม่พบข้อมูล</h3>
            <p class="mt-1 text-sm text-gray-500">${escapeHTML(message)}</p>
        </div>
    `;
}

// --- Function to manage the confirmation modal ---
export function showConfirmModal(title, message, onConfirm) {
    const modal = document.getElementById('confirm-modal');
    const titleEl = document.getElementById('confirm-modal-title');
    const messageEl = document.getElementById('confirm-modal-message');
    const confirmBtn = document.getElementById('confirm-modal-confirm-btn');
    const cancelBtn = document.getElementById('confirm-modal-cancel-btn');

    if (!modal || !titleEl || !messageEl || !confirmBtn || !cancelBtn) return;

    titleEl.textContent = title;
    messageEl.textContent = message;

    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

    const confirmHandler = () => {
        onConfirm();
        modal.classList.remove('active');
    };

    const cancelHandler = () => {
        modal.classList.remove('active');
    };

    newConfirmBtn.addEventListener('click', confirmHandler, { once: true });
    cancelBtn.addEventListener('click', cancelHandler, { once: true });

    modal.classList.add('active');
}


// --- Helper function to render pagination controls ---
function renderPagination(containerId, totalItems, currentPage, onPageChange) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';

    const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE);
    if (totalPages <= 1) return;

    const prevButton = document.createElement('button');
    prevButton.textContent = '‹ ก่อนหน้า';
    prevButton.disabled = currentPage === 1;
    prevButton.className = 'px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed';
    prevButton.addEventListener('click', () => onPageChange(currentPage - 1));

    const pageInfo = document.createElement('span');
    pageInfo.textContent = `หน้า ${currentPage} จาก ${totalPages}`;
    pageInfo.className = 'text-sm text-gray-600';

    const nextButton = document.createElement('button');
    nextButton.textContent = 'ถัดไป ›';
    nextButton.disabled = currentPage === totalPages;
    nextButton.className = 'px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed';
    nextButton.addEventListener('click', () => onPageChange(currentPage + 1));

    container.appendChild(prevButton);
    container.appendChild(pageInfo);
    container.appendChild(nextButton);
}

export function showMessage(message, isSuccess = true) {
    if (!window.messageArea) return;
    window.messageArea.textContent = message;
    window.messageArea.className = `mb-4 text-center p-3 rounded-lg ${isSuccess ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`;
    setTimeout(() => { if(window.messageArea) { window.messageArea.innerHTML = ''; window.messageArea.className = 'mb-4 text-center'; } }, 5000);
}

export function populateRankDropdowns() {
    const ranks = {
        'นายทหารสัญญาบัตร (ชาย)': ['น.อ.(พ)', 'น.อ.หม่อมหลวง', 'น.อ.', 'น.ท.', 'น.ต.', 'ร.อ.', 'ร.ท.', 'ร.ต.'],
        'นายทหารสัญญาบัตร (หญิง)': ['น.อ.(พ).หญิง', 'น.อ.หญิง', 'น.ท.หญิง', 'น.ต.หญิง', 'ร.อ.หญิง', 'ร.ท.หญิง', 'ร.ต.หญิง'],
        'นายทหารประทวน (ชาย)': ['พ.อ.อ.(พ)', 'พ.อ.อ.', 'พ.อ.ท.', 'พ.อ.ต.', 'จ.อ.', 'จ.ท.', 'จ.ต.'],
        'นายทหารประทวน (หญิง)': ['พ.อ.อ.หญิง', 'พ.อ.ท.หญิง', 'พ.อ.ต.หญิง', 'จ.อ.หญิง', 'จ.ท.หญิง', 'จ.ต.หญิง'],
        'พลเรือน': ['นาย', 'นาง', 'นางสาว']
    };
    const rankSelects = [document.getElementById('person-rank'), document.getElementById('user-rank')];
    rankSelects.forEach(select => {
        if (!select) return;
        select.innerHTML = '<option value="">-- กรุณาเลือก --</option>';
        for (const groupName in ranks) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = groupName;
            ranks[groupName].forEach(rank => {
                const option = document.createElement('option');
                option.value = rank;
                option.textContent = rank;
                optgroup.appendChild(option);
            });
            select.appendChild(optgroup);
        }
    });
}

export function renderDashboard(res) {
    const summary = res.summary;
    if (!summary) return;
    const totalPersonnelEl = document.getElementById('dashboard-total-personnel');
    const onDutyEl = document.getElementById('dashboard-on-duty');
    const statusSummaryArea = document.getElementById('dashboard-status-summary');
    const deptStatusArea = document.getElementById('dashboard-department-status');
    const weekRangeEl = document.getElementById('dashboard-week-range');

    if(totalPersonnelEl) totalPersonnelEl.textContent = summary.total_personnel || '0';
    if(onDutyEl) onDutyEl.textContent = summary.total_on_duty || '0';
    
    if (weekRangeEl && summary.weekly_date_range) {
        weekRangeEl.textContent = `(${summary.weekly_date_range})`;
    }

    if(statusSummaryArea) {
        statusSummaryArea.innerHTML = '';
        if (summary.status_summary && Object.keys(summary.status_summary).length > 0) {
            for (const [status, count] of Object.entries(summary.status_summary)) {
                const p = document.createElement('p');
                p.textContent = `${escapeHTML(status)}: ${count} นาย`;
                statusSummaryArea.appendChild(p);
            }
        } else {
            statusSummaryArea.textContent = 'ยังไม่มีรายงาน';
        }
    }

    if(deptStatusArea) {
        deptStatusArea.innerHTML = '';
        if (summary.all_departments && summary.all_departments.length > 0) {
            summary.all_departments.forEach(dept => {
                const submission = summary.submitted_info[dept];
                const isSubmitted = !!submission;
                const card = document.createElement('div');
                card.className = `p-3 rounded-lg border ${isSubmitted ? 'bg-green-100 border-green-300' : 'bg-red-100 border-red-300'}`;
                
                let statusLine = isSubmitted ? `<p class="text-xs text-green-600">ส่งแล้ว (มีสถานะ ${submission.status_count} นาย)</p>` : `<p class="text-xs text-red-600">ยังไม่ส่ง</p>`;
                let detailsLine = isSubmitted ? `<p class="text-xs text-gray-500 mt-1">โดย: ${escapeHTML(submission.submitter_fullname)} (${new Date(submission.timestamp).toLocaleString('th-TH', { dateStyle: 'short', timeStyle: 'short' })} น.)</p>` : '';

                card.innerHTML = `<p class="font-semibold text-sm ${isSubmitted ? 'text-green-800' : 'text-red-800'}">${escapeHTML(dept)}</p>${statusLine}${detailsLine}`;
                deptStatusArea.appendChild(card);
            });
        } else {
            deptStatusArea.innerHTML = '<p class="text-gray-500 col-span-full">ไม่พบข้อมูลแผนก</p>';
        }
    }
}

export function renderPersonnel(res) {
    if(!window.personnelListArea) return;
    const { personnel, total, page } = res;
    window.personnelListArea.innerHTML = '';
    
    if (!personnel || personnel.length === 0) {
        const emptyRow = `<tr><td colspan="8">${createEmptyState('ไม่พบข้อมูลกำลังพลที่ตรงกับคำค้นหา')}</td></tr>`;
        window.personnelListArea.innerHTML = emptyRow;
        document.getElementById('personnel-pagination').innerHTML = '';
        return;
    }
    
    const startNumber = (page - 1) * ITEMS_PER_PAGE + 1;
    personnel.forEach((p, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `<td class="px-4 py-2">${startNumber + index}</td>
                         <td class="px-4 py-2">${escapeHTML(p.rank)}</td>
                         <td class="px-4 py-2">${escapeHTML(p.first_name)}</td>
                         <td class="px-4 py-2">${escapeHTML(p.last_name)}</td>
                         <td class="px-4 py-2">${escapeHTML(p.position)}</td>
                         <td class="px-4 py-2">${escapeHTML(p.specialty)}</td>
                         <td class="px-4 py-2">${escapeHTML(p.department)}</td>
                         <td class="px-4 py-2 whitespace-nowrap">
                            <button data-id='${escapeHTML(p.id)}' class="edit-person-btn text-blue-600 hover:text-blue-900 mr-2">แก้ไข</button>
                            <button data-id='${escapeHTML(p.id)}' class="delete-person-btn text-red-600 hover:text-red-900">ลบ</button>
                         </td>`;
        window.personnelListArea.appendChild(row);
    });

    renderPagination('personnel-pagination', total, page, (newPage) => {
        window.personnelCurrentPage = newPage;
        window.loadDataForPane('pane-personnel');
    });
}

export function renderUsers(res) {
    if(!window.userListArea) return;
    const { users, total, page } = res;
    window.userListArea.innerHTML = '';
    
    if (!users || users.length === 0) {
        const emptyRow = `<tr><td colspan="6">${createEmptyState('ไม่พบข้อมูลผู้ใช้ที่ตรงกับคำค้นหา')}</td></tr>`;
        window.userListArea.innerHTML = emptyRow;
        document.getElementById('user-pagination').innerHTML = '';
        return;
    }
    
    users.forEach(u => {
        const row = document.createElement('tr');
        const roleText = u.role === 'admin' ? 'Admin' : 'User';
        const roleClass = u.role === 'admin' ? 'text-red-600 font-semibold' : 'text-gray-600';
        row.innerHTML = `<td class="px-4 py-2 font-mono">${escapeHTML(u.username)}</td>
                         <td class="px-4 py-2">${escapeHTML(u.rank)} ${escapeHTML(u.first_name)} ${escapeHTML(u.last_name)}</td>
                         <td class="px-4 py-2">${escapeHTML(u.position)}</td>
                         <td class="px-4 py-2">${escapeHTML(u.department)}</td>
                         <td class="px-4 py-2 ${roleClass}">${escapeHTML(roleText)}</td>
                         <td class="px-4 py-2 whitespace-nowrap">
                            <button data-username='${escapeHTML(u.username)}' class="edit-user-btn text-blue-600 hover:text-blue-900 mr-2">แก้ไข</button>
                            <button data-username='${escapeHTML(u.username)}' class="delete-user-btn text-red-600 hover:text-red-900">ลบ</button>
                         </td>`;
        window.userListArea.appendChild(row);
    });

    renderPagination('user-pagination', total, page, (newPage) => {
        window.userCurrentPage = newPage;
        window.loadDataForPane('pane-admin');
    });
}

export function renderStatusSubmissionForm(res) {
    const { personnel, submission_status, weekly_date_range, persistent_statuses = [], all_departments = [] } = res;

    const selectorContainer = document.getElementById('admin-dept-selector-container');
    const bulkButtonContainer = document.getElementById('bulk-status-buttons');
    const submissionInfoArea = document.getElementById('submission-info-area');
    const submissionForm = document.getElementById('submission-form-section');

    if (!selectorContainer || !bulkButtonContainer || !window.statusSubmissionListArea || !window.submitStatusTitle || !submissionInfoArea || !submissionForm) return;

    if (window.currentUser.role !== 'admin' && submission_status && !window.editingReportData) {
        const submittedTime = new Date(submission_status.timestamp).toLocaleString('th-TH');
        submissionInfoArea.innerHTML = `คุณได้ส่งยอดสำหรับรอบนี้ไปแล้วเมื่อ ${submittedTime} น.`;
        submissionInfoArea.classList.remove('hidden');
        submissionForm.classList.add('hidden');
        bulkButtonContainer.classList.add('hidden');
        selectorContainer.classList.add('hidden');
        window.submitStatusTitle.textContent = `สถานะการส่งยอด`;
        return;
    }
    
    submissionInfoArea.classList.add('hidden');
    submissionForm.classList.remove('hidden');
    bulkButtonContainer.classList.remove('hidden');
    selectorContainer.classList.remove('hidden');

    const updateRowHighlight = (selectElement) => {
        const row = selectElement.closest('tr');
        row.classList.toggle('row-selected', selectElement.value !== 'ไม่มี');
    };

    const setAllStatus = (status) => {
        window.statusSubmissionListArea.querySelectorAll('tr').forEach(row => {
            const statusSelect = row.querySelector('.status-select');
            if (statusSelect) {
                statusSelect.value = status;
                statusSelect.dispatchEvent(new Event('change'));

                if (status === 'ไม่มี') {
                    const detailsInput = row.querySelector('.details-input');
                    if (detailsInput) detailsInput.value = '';

                    const startDateInput = row.querySelector('.start-date-input');
                    if (startDateInput && startDateInput._flatpickr) {
                        startDateInput._flatpickr.clear();
                    }

                    const endDateInput = row.querySelector('.end-date-input');
                    if (endDateInput && endDateInput._flatpickr) {
                        endDateInput._flatpickr.clear();
                    }
                }
            }
        });
    };

    bulkButtonContainer.innerHTML = '';
    const bulkActions = [{ label: 'ล้างค่า ทั้งหมด', value: 'ไม่มี', class: 'bg-gray-400 hover:bg-gray-500' }];
    bulkActions.forEach(action => {
        const button = document.createElement('button');
        button.textContent = action.label;
        button.className = `text-white font-bold py-1 px-3 text-sm rounded-lg ${action.class}`;
        button.addEventListener('click', () => setAllStatus(action.value));
        bulkButtonContainer.appendChild(button);
    });

    const displayPersonnelForDept = (dept) => {
        const itemsToPreFill = window.editingReportData ? window.editingReportData.items : persistent_statuses.filter(s => s.department === dept);

        window.submitStatusTitle.innerHTML = `ส่งยอดกำลังพล แผนก ${escapeHTML(dept)}`;
        if (weekly_date_range) {
            const weekRangeEl = document.createElement('span');
            weekRangeEl.className = 'text-lg text-gray-500 font-normal ml-2';
            weekRangeEl.textContent = `(${weekly_date_range})`;
            window.submitStatusTitle.appendChild(weekRangeEl);
        }

        window.statusSubmissionListArea.innerHTML = '';
        const personnelInDept = personnel.filter(p => p.department === dept);

        if (personnelInDept.length === 0) {
            window.statusSubmissionListArea.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-gray-500">ไม่พบข้อมูลกำลังพลในแผนกนี้</td></tr>';
            return;
        }

        personnelInDept.forEach((p, index) => {
            const personnelName = `${escapeHTML(p.rank)} ${escapeHTML(p.first_name)} ${escapeHTML(p.last_name)}`;
            
            const statusesToRender = itemsToPreFill.filter(item => item.personnel_id === p.id);

            if (statusesToRender.length === 0) {
                statusesToRender.push({ status: 'ไม่มี', details: '', start_date: '', end_date: '' });
            }

            statusesToRender.forEach((statusData, statusIndex) => {
                const row = document.createElement('tr');
                row.dataset.personnelId = escapeHTML(p.id);
                row.dataset.personnelName = personnelName;

                if (statusIndex === 0) {
                    row.innerHTML = `
                        <td class="px-4 py-2">${index + 1}</td>
                        <td class="px-4 py-2 font-semibold">${personnelName}</td>
                        <td class="px-4 py-2">
                            <select class="status-select w-full border rounded px-2 py-1 bg-white"></select>
                        </td>
                        <td class="px-4 py-2"><input type="text" class="details-input w-full border rounded px-2 py-1" placeholder="รายละเอียด/สถานที่..."></td>
                        <td class="px-4 py-2"><input type="text" class="start-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
                        <td class="px-4 py-2"><input type="text" class="end-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
                        <td class="px-4 py-2">
                            <button type="button" class="add-status-btn bg-green-500 hover:bg-green-600 text-white font-bold py-1 px-2 rounded-full text-xs">+</button>
                        </td>
                    `;
                } else {
                    row.innerHTML = `
                        <td class="px-4 py-2"></td>
                        <td class="px-4 py-2 text-right text-gray-500 pr-4">↳</td>
                        <td class="px-4 py-2">
                            <select class="status-select w-full border rounded px-2 py-1 bg-white"></select>
                        </td>
                        <td class="px-4 py-2"><input type="text" class="details-input w-full border rounded px-2 py-1" placeholder="รายละเอียด/สถานที่..."></td>
                        <td class="px-4 py-2"><input type="text" class="start-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
                        <td class="px-4 py-2"><input type="text" class="end-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
                        <td class="px-4 py-2">
                            <button type="button" class="remove-status-btn bg-red-500 hover:bg-red-600 text-white font-bold py-1 px-2 rounded-full text-xs">-</button>
                        </td>
                    `;
                }
                
                window.statusSubmissionListArea.appendChild(row);

                const statusSelect = row.querySelector('.status-select');
                statusSelect.innerHTML = `
                    <option value="ไม่มี">ไม่มี</option>
                    <option value="ราชการ">ราชการ</option>
                    <option value="คุมงาน">คุมงาน</option>
                    <option value="ศึกษา">ศึกษา</option>
                    <option value="ลากิจ">ลากิจ</option>
                    <option value="ลาพักผ่อน">ลาพักผ่อน</option>
                `;
                statusSelect.value = statusData.status || 'ไม่มี';
                row.querySelector('.details-input').value = statusData.details || '';
                
                statusSelect.addEventListener('change', () => updateRowHighlight(statusSelect));
                updateRowHighlight(statusSelect);

                const flatpickrConfig = {
                    locale: thai_locale, 
                    altInput: true,
                    altFormat: "j F Y",
                    dateFormat: "Y-m-d",
                    allowInput: true
                };

                const startDatePicker = flatpickr(row.querySelector('.start-date-input'), flatpickrConfig);
                const endDatePicker = flatpickr(row.querySelector('.end-date-input'), flatpickrConfig);
                
                if (statusData.start_date) startDatePicker.setDate(statusData.start_date);
                if (statusData.end_date) endDatePicker.setDate(statusData.end_date);
            });
        });
    };

    if (window.currentUser.role === 'admin') {
        selectorContainer.innerHTML = '';
        const label = document.createElement('label');
        label.htmlFor = 'admin-dept-selector';
        label.className = 'block text-sm font-medium text-gray-700 mb-1';
        label.textContent = 'เลือกแผนกเพื่อส่งยอด';
        const selector = document.createElement('select');
        selector.id = 'admin-dept-selector';
        selector.className = 'w-full md:w-1/3 border rounded px-2 py-2 bg-white shadow-sm';
        
        let currentDept = window.editingReportData ? window.editingReportData.department : (all_departments.length > 0 ? all_departments[0] : '');

        all_departments.forEach(dept => {
            const option = document.createElement('option');
            option.value = dept;
            option.textContent = dept;
            if (dept === currentDept) {
                option.selected = true;
            }
            selector.appendChild(option);
        });
        selectorContainer.appendChild(label);
        selectorContainer.appendChild(selector);
        
        displayPersonnelForDept(currentDept);
        if (window.editingReportData) delete window.editingReportData;

        selector.addEventListener('change', (e) => {
            displayPersonnelForDept(e.target.value);
        });
    } else {
        selectorContainer.innerHTML = '';
        const dept = window.editingReportData ? window.editingReportData.department : window.currentUser.department;
        displayPersonnelForDept(dept);
        if (window.editingReportData) delete window.editingReportData;
    }
}

export function addStatusRow(clickedButton) {
    const mainRow = clickedButton.closest('tr');
    const newRow = document.createElement('tr');
    newRow.dataset.personnelId = mainRow.dataset.personnelId;
    newRow.dataset.personnelName = mainRow.dataset.personnelName;

    newRow.innerHTML = `
        <td class="px-4 py-2"></td>
        <td class="px-4 py-2 text-right text-gray-500 pr-4">↳</td>
        <td class="px-4 py-2">
            <select class="status-select w-full border rounded px-2 py-1 bg-white">
                <option value="ไม่มี">ไม่มี</option>
                <option value="ราชการ">ราชการ</option>
                <option value="คุมงาน">คุมงาน</option>
                <option value="ศึกษา">ศึกษา</option>
                <option value="ลากิจ">ลากิจ</option>
                <option value="ลาพักผ่อน">ลาพักผ่อน</option>
            </select>
        </td>
        <td class="px-4 py-2"><input type="text" class="details-input w-full border rounded px-2 py-1" placeholder="รายละเอียด/สถานที่..."></td>
        <td class="px-4 py-2"><input type="text" class="start-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
        <td class="px-4 py-2"><input type="text" class="end-date-input w-full border rounded px-2 py-1" placeholder="เลือกวันที่..."></td>
        <td class="px-4 py-2">
            <button type="button" class="remove-status-btn bg-red-500 hover:bg-red-600 text-white font-bold py-1 px-2 rounded-full text-xs">-</button>
        </td>
    `;

    mainRow.parentNode.insertBefore(newRow, mainRow.nextSibling);

    const flatpickrConfig = {
        locale: thai_locale, 
        altInput: true,
        altFormat: "j F Y",
        dateFormat: "Y-m-d",
        allowInput: true
    };
    flatpickr(newRow.querySelector('.start-date-input'), flatpickrConfig);
    flatpickr(newRow.querySelector('.end-date-input'), flatpickrConfig);
}


export function renderWeeklyReport(res) {
    const reports = res.reports; 
    const weekly_date_range = res.weekly_date_range;
    const all_departments = res.all_departments || [];
    const submitted_departments = res.submitted_departments || [];

    const weekRangeEl = document.getElementById('report-week-range');
    if (weekRangeEl && weekly_date_range) {
        weekRangeEl.textContent = `(${weekly_date_range})`;
    } else if (weekRangeEl) {
        weekRangeEl.textContent = '';
    }

    const exportArchiveBtn = document.getElementById('export-archive-btn');
    if (exportArchiveBtn) {
        const allSubmitted = all_departments.length > 0 && all_departments.every(dept => submitted_departments.includes(dept));
        if (allSubmitted) {
            exportArchiveBtn.disabled = false;
            exportArchiveBtn.classList.remove('bg-gray-400', 'cursor-not-allowed');
            exportArchiveBtn.classList.add('bg-blue-500', 'hover:bg-blue-700');
            exportArchiveBtn.title = 'ส่งออกรายงานทั้งหมดเป็นไฟล์ Excel และเก็บเข้าสู่ระบบถาวร';
        } else {
            exportArchiveBtn.disabled = true;
            exportArchiveBtn.classList.add('bg-gray-400', 'cursor-not-allowed');
            exportArchiveBtn.classList.remove('bg-blue-500', 'hover:bg-blue-700');
            exportArchiveBtn.title = 'ต้องรอให้ทุกแผนกส่งรายงานก่อนจึงจะสามารถส่งออกได้';
        }
    }

    if(!window.reportContainer) return;
    window.reportContainer.innerHTML = '';
    window.currentWeeklyReports = reports;
    if (!reports || reports.length === 0) {
        window.reportContainer.innerHTML = createEmptyState('ยังไม่มีแผนกใดส่งรายงานประจำสัปดาห์');
        return;
    }
    const reportsByDept = reports.reduce((acc, report) => {
        const dept = report.department || 'ไม่ระบุแผนก';
        if (!acc[dept]) {
            acc[dept] = { 
                submitterName: `${escapeHTML(report.rank)} ${escapeHTML(report.first_name)} ${escapeHTML(report.last_name)}`, 
                timestamp: report.timestamp, 
                items: [],
                id: report.id
            };
        }
        acc[dept].items.push(...report.items);
        return acc;
    }, {});
    
    window.reportContainer.className = 'space-y-6';

    for (const department in reportsByDept) {
        const deptReport = reportsByDept[department];
        const reportWrapper = document.createElement('div');
        reportWrapper.className = 'p-4 border rounded-lg bg-gray-50';
        const itemsHtml = deptReport.items.map((item, index) => `<tr class="border-t"><td class="py-2 pr-2 text-center">${index + 1}</td><td class="py-2 px-2">${escapeHTML(item.personnel_name)}</td><td class="py-2 px-2 text-blue-600">${escapeHTML(item.status)}</td><td class="py-2 px-2 text-gray-600">${escapeHTML(item.details) || '-'}</td><td class="py-2 pl-2 text-gray-600">${formatThaiDateRangeArabic(item.start_date, item.end_date)}</td></tr>`).join('');
        const submittedTime = new Date(deptReport.timestamp).toLocaleString('th-TH');
        
        const editButtonHtml = `<button data-id="${deptReport.id}" class="edit-weekly-report-btn bg-yellow-500 hover:bg-yellow-600 text-white text-sm font-bold py-1 px-3 rounded-lg">แก้ไข</button>`;

        reportWrapper.innerHTML = `
            <div class="flex flex-wrap justify-between items-center mb-3 gap-2">
                <div>
                    <h3 class="text-lg font-semibold text-gray-700">แผนก: ${escapeHTML(department)}</h3>
                    <p class="text-sm text-gray-500">ส่งโดย: ${deptReport.submitterName}</p>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="text-sm text-gray-500">ส่งล่าสุดเมื่อ: ${submittedTime} น.</span>
                    ${editButtonHtml}
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full bg-white text-sm">
                    <thead>
                        <tr>
                            <th class="text-center font-medium text-gray-500 uppercase pb-1 w-[5%]">ลำดับ</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[30%]">ชื่อ-สกุล</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[15%]">สถานะ</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[30%]">รายละเอียด</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[20%]">ช่วงวันที่</th>
                        </tr>
                    </thead>
                    <tbody>${itemsHtml}</tbody>
                </table>
            </div>`;
        window.reportContainer.appendChild(reportWrapper);
    }
}

export function renderSubmissionHistory(res) {
    const history = res.history;
    window.allHistoryData = history || {};
    populateHistorySelectors(window.allHistoryData);
    if(window.historyContainer) window.historyContainer.innerHTML = createEmptyState('กรุณาเลือกปีและเดือนเพื่อแสดงประวัติ');
}

export function populateHistorySelectors(history) {
    const yearSelect = document.getElementById('history-year-select');
    const monthSelect = document.getElementById('history-month-select');
    if(!yearSelect || !monthSelect) return;
    
    yearSelect.innerHTML = '<option value="">เลือกปี</option>';
    monthSelect.innerHTML = '<option value="">เลือกเดือน</option>';

    if (history && Object.keys(history).length > 0) {
        const sortedYears = Object.keys(history).sort((a, b) => b - a);
        sortedYears.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearSelect.appendChild(option);
        });
    }
}

export function renderFilteredHistoryReports(reports) {
    const historyContainer = document.getElementById('history-container');
    if (!historyContainer) return;
    historyContainer.innerHTML = '';

    if (!reports || reports.length === 0) {
        historyContainer.innerHTML = createEmptyState('ไม่พบประวัติการส่งรายงานสำหรับเดือนที่เลือก');
        return;
    }

    reports.forEach(report => {
        const reportWrapper = document.createElement('div');
        reportWrapper.className = 'p-4 border rounded-lg bg-gray-50 mb-4';
        const itemsHtml = report.items.map((item, index) => `<tr class="border-t"><td class="py-2 pr-2 text-center">${index + 1}</td><td class="py-2 px-2">${escapeHTML(item.personnel_name)}</td><td class="py-2 px-2 text-blue-600">${escapeHTML(item.status)}</td><td class="py-2 px-2 text-gray-600">${escapeHTML(item.details) || '-'}</td><td class="py-2 pl-2 text-gray-600">${formatThaiDateRangeArabic(item.start_date, item.end_date)}</td></tr>`).join('');
        
        const editButtonHtml = report.source === 'active' 
            ? `<button data-id="${report.id}" class="edit-history-btn bg-blue-500 hover:bg-blue-600 text-white text-sm font-bold py-1 px-3 rounded-lg">แก้ไข</button>` 
            : `<span class="text-sm text-gray-400">(เก็บถาวรแล้ว)</span>`;

        reportWrapper.innerHTML = `
            <div class="flex flex-wrap justify-between items-center mb-3 gap-2">
                <div>
                    <h4 class="text-lg font-semibold text-gray-800">รายงานวันที่ ${formatThaiDateArabic(report.date)}</h4>
                    <span class="text-sm text-gray-500">ส่งเมื่อ: ${new Date(report.timestamp).toLocaleString('th-TH')}</span>
                </div>
                ${editButtonHtml}
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full bg-white text-sm">
                    <thead>
                        <tr>
                            <th class="text-center font-medium text-gray-500 uppercase pb-1 w-[5%]">ลำดับ</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[30%]">ชื่อ-สกุล</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[15%]">สถานะ</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[30%]">รายละเอียด</th>
                            <th class="text-left font-medium text-gray-500 uppercase pb-1 w-[20%]">ช่วงวันที่</th>
                        </tr>
                    </thead>
                    <tbody>${itemsHtml}</tbody>
                </table>
            </div>`;
        historyContainer.appendChild(reportWrapper);
    });
}


export function populateArchiveSelectors(archives) {
    if(!window.archiveYearSelect || !window.archiveMonthSelect) return;
    window.archiveYearSelect.innerHTML = '<option value="">เลือกปี</option>';
    window.archiveMonthSelect.innerHTML = '<option value="">เลือกเดือน</option>';
    if (archives && Object.keys(archives).length > 0) {
        const sortedYears = Object.keys(archives).sort((a, b) => b - a);
        sortedYears.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = parseInt(year) + 543;
            window.archiveYearSelect.appendChild(option);
        });
    }
}

export function renderArchivedReports(reports) {
    if(!window.archiveContainer) return;
    window.archiveContainer.innerHTML = '';
    if (!reports || reports.length === 0) {
        window.archiveContainer.innerHTML = createEmptyState('ไม่พบรายงานที่เก็บถาวรสำหรับเดือนที่เลือก');
        return;
    }
    const reportsByDate = reports.reduce((acc, report) => {
        const date = report.date;
        if (!acc[date]) acc[date] = [];
        acc[date].push(report);
        return acc;
    }, {});
    Object.keys(reportsByDate).sort((a, b) => new Date(b) - new Date(a)).forEach(date => {
        const dateCard = document.createElement('div');
        dateCard.className = 'mb-6 p-4 border rounded-lg bg-gray-50';
        let reportsHtml = '';
        reportsByDate[date].forEach(report => {
            const itemsHtml = report.items.map((item, index) => `<tr class="border-t"><td class="py-2 pr-2 text-center">${index + 1}</td><td class="py-2 px-2">${escapeHTML(item.personnel_name)}</td><td class="py-2 px-2 text-blue-600">${escapeHTML(item.status)}</td><td class="py-2 px-2 text-gray-600">${escapeHTML(item.details) || '-'}</td><td class="py-2 pl-2 text-gray-600">${formatThaiDateRangeArabic(item.start_date, item.end_date)}</td></tr>`).join('');
            reportsHtml += `<div class="mt-4"><div class="flex justify-between items-center text-sm text-gray-500 mb-2"><span>แผนก: ${escapeHTML(report.department || '')}</span><span>ส่งโดย: ${escapeHTML(report.submitted_by)}</span></div><table class="min-w-full bg-white text-sm"><thead><tr><th class="text-center font-medium text-gray-500 uppercase pb-1 w-[5%]">ลำดับ</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[30%]">ชื่อ-สกุล</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[15%]">สถานะ</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[30%]">รายละเอียด</th><th class="text-left font-medium text-gray-500 uppercase pb-1 w-[20%]">ช่วงวันที่</th></tr></thead><tbody>${itemsHtml}</tbody></table></div>`;
        });
        dateCard.innerHTML = `<div class="flex justify-between items-center"><h3 class="text-lg font-semibold text-gray-800">ประวัติการเก็บรายงาน วันที่ ${formatThaiDateArabic(date)}</h3><button class="download-daily-archive-btn bg-gray-200 hover:bg-gray-300 text-gray-700 text-xs py-1 px-2 rounded" data-date="${escapeHTML(date)}">ดาวน์โหลดของวันนี้</button></div>${reportsHtml}`;
        window.archiveContainer.appendChild(dateCard);
    });
}

export function openPersonnelModal(person = null) {
    window.personnelForm.reset();
    const title = window.personnelForm.querySelector('#personnel-modal-title');
    if (person) {
        title.textContent = 'แก้ไขข้อมูลกำลังพล';
        window.personnelForm.querySelector('#person-id').value = person.id;
        window.personnelForm.querySelector('#person-rank').value = person.rank;
        window.personnelForm.querySelector('#person-first-name').value = person.first_name;
        window.personnelForm.querySelector('#person-last-name').value = person.last_name;
        window.personnelForm.querySelector('#person-position').value = person.position;
        window.personnelForm.querySelector('#person-specialty').value = person.specialty;
        window.personnelForm.querySelector('#person-department').value = person.department;
    } else {
        title.textContent = 'เพิ่มข้อมูลกำลังพล';
        window.personnelForm.querySelector('#person-id').value = '';
    }
    window.personnelModal.classList.add('active');
}

export function openUserModal(user = null) {
    window.userForm.reset();
    const usernameInput = window.userForm.querySelector('#user-username');
    if (user) {
        window.userModalTitle.textContent = 'แก้ไขข้อมูลผู้ใช้';
        usernameInput.value = user.username;
        usernameInput.readOnly = true;
        usernameInput.classList.add('bg-gray-200');
        window.userForm.querySelector('#user-rank').value = user.rank;
        window.userForm.querySelector('#user-first-name').value = user.first_name;
        window.userForm.querySelector('#user-last-name').value = user.last_name;
        window.userForm.querySelector('#user-position').value = user.position;
        window.userForm.querySelector('#user-department').value = user.department;
        window.userForm.querySelector('#user-role').value = user.role;
    } else {
        window.userModalTitle.textContent = 'เพิ่มผู้ใช้ใหม่';
        usernameInput.readOnly = false;
        usernameInput.classList.remove('bg-gray-200');
    }
    window.userModal.classList.add('active');
}

// A global variable to hold the full dataset for filtering
let fullStatusDataCache = null;

// Function to update the view based on the selected filter
function updateActiveStatusesView(filter) {
    if (!fullStatusDataCache) return;

    // Update button styles
    document.querySelectorAll('.status-filter-btn').forEach(btn => {
        if (btn.dataset.filter === filter) {
            btn.classList.add('bg-blue-600', 'text-white', 'border-blue-600');
            btn.classList.remove('bg-white', 'text-gray-700', 'border-gray-300');
        } else {
            btn.classList.remove('bg-blue-600', 'text-white', 'border-blue-600');
            btn.classList.add('bg-white', 'text-gray-700', 'border-gray-300');
        }
    });

    const { active_statuses, available_personnel, total_personnel } = fullStatusDataCache;
    const unavailableContainer = document.getElementById('active-statuses-container');
    const availableContainer = document.getElementById('available-personnel-container');
    const chartContainer = document.getElementById('status-chart-container');
    const unavailableTitle = document.getElementById('unavailable-title');
    const availableTitle = document.getElementById('available-title');

    // Filter data
    let filteredUnavailable = active_statuses;
    let filteredAvailable = available_personnel;
    let showUnavailable = true;
    let showAvailable = true;

    if (filter === 'ว่าง') {
        filteredUnavailable = [];
        showUnavailable = false;
    } else if (filter !== 'ทั้งหมด') {
        filteredUnavailable = active_statuses.filter(s => s.status === filter);
        filteredAvailable = [];
        showAvailable = false;
    }

    // --- Chart Logic (Update based on filter) ---
    chartContainer.innerHTML = '<canvas id="status-chart-canvas"></canvas>';
    const unavailable_count = filteredUnavailable.length;
    const available_count = showAvailable ? filteredAvailable.length : 0;
    
    const status_counts = filteredUnavailable.reduce((acc, s) => {
        acc[s.status] = (acc[s.status] || 0) + 1;
        return acc;
    }, {});

    let chartLabels = [];
    let chartData = [];
    
    if (showAvailable && available_count > 0) {
        chartLabels.push('ว่าง');
        chartData.push(available_count);
    }
    chartLabels.push(...Object.keys(status_counts));
    chartData.push(...Object.values(status_counts));
    
    // Dynamically create the color array based on the labels
    const dynamicChartColors = chartLabels.map(label => CHART_STATUS_COLORS[label] || '#CCCCCC'); // Use gray for any unknown status

    const ctx = document.getElementById('status-chart-canvas').getContext('2d');
    if (window.myStatusChart) {
        window.myStatusChart.destroy();
    }
    
    const centerTextPlugin = {
        id: 'centerText',
        afterDraw: (chart) => {
            const { ctx } = chart;
            const chartArea = chart.chartArea;
            const x = (chartArea.left + chartArea.right) / 2;
            const y = (chartArea.top + chartArea.bottom) / 2;
            
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            
            ctx.font = "bold 1.2rem 'Kanit', sans-serif";
            ctx.fillStyle = '#4B5563';
            ctx.fillText('กำลังพลทั้งหมด', x, y - 30);
            
            ctx.font = "bold 2.5rem 'Kanit', sans-serif";
            ctx.fillStyle = '#1F2937';
            ctx.fillText(total_personnel, x, y + 5);

            ctx.font = "1rem 'Kanit', sans-serif";
            ctx.fillStyle = '#6B7280';
            ctx.fillText(`ว่าง ${available_personnel.length} | ติดภารกิจ ${active_statuses.length}`, x, y + 40);

            ctx.restore();
        }
    };

    Chart.register(ChartDataLabels, centerTextPlugin);

    window.myStatusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: chartLabels,
            datasets: [{
                label: 'จำนวนกำลังพล',
                data: chartData,
                backgroundColor: dynamicChartColors,
                borderColor: '#FFFFFF',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: { font: { family: "'Kanit', sans-serif", size: 14 }, boxWidth: 20 }
                },
                title: { display: false },
                datalabels: {
                    formatter: (value) => value > 0 ? value : '',
                    color: '#fff',
                    font: { family: "'Kanit', sans-serif", weight: 'bold', size: 14 },
                    textStrokeColor: 'black',
                    textStrokeWidth: 2
                }
            }
        }
    });

    // --- Table Logic (Update based on filter) ---
    unavailableTitle.style.display = showUnavailable ? 'block' : 'none';
    unavailableContainer.style.display = showUnavailable ? 'block' : 'none';
    availableTitle.style.display = showAvailable ? 'block' : 'none';
    availableContainer.style.display = showAvailable ? 'block' : 'none';

    if (showUnavailable) {
        if (!filteredUnavailable || filteredUnavailable.length === 0) {
            unavailableContainer.innerHTML = createEmptyState('ไม่พบกำลังพลที่ติดภารกิจตามเงื่อนไขที่เลือก');
        } else {
            const is_admin = (window.currentUser.role === 'admin');
            let tableHTML = `<table class="min-w-full bg-white"><thead class="bg-gray-50"><tr>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ลำดับ</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ยศ-ชื่อ-สกุล</th>
                ${is_admin ? '<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">แผนก</th>' : ''}
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">สถานะ</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">รายละเอียด/สถานที่</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ช่วงวันที่</th>
            </tr></thead><tbody class="bg-white divide-y divide-gray-200">`;
            filteredUnavailable.forEach((s, index) => {
                const fullName = `${escapeHTML(s.rank)} ${escapeHTML(s.first_name)} ${escapeHTML(s.last_name)}`;
                const bgColorClass = STATUS_COLORS[s.status] || '';
                tableHTML += `<tr class="${bgColorClass}">
                    <td class="px-4 py-2">${index + 1}</td>
                    <td class="px-4 py-2">${fullName}</td>
                    ${is_admin ? `<td class="px-4 py-2">${escapeHTML(s.department)}</td>` : ''}
                    <td class="px-4 py-2">${escapeHTML(s.status)}</td>
                    <td class="px-4 py-2">${escapeHTML(s.details)}</td>
                    <td class="px-4 py-2">${formatThaiDateRangeArabic(s.start_date, s.end_date)}</td>
                </tr>`;
            });
            tableHTML += `</tbody></table>`;
            unavailableContainer.innerHTML = tableHTML;
        }
    }

    if (showAvailable) {
        if (!filteredAvailable || filteredAvailable.length === 0) {
            availableContainer.innerHTML = createEmptyState('ไม่พบกำลังพลที่ว่าง');
        } else {
            const is_admin = (window.currentUser.role === 'admin');
            let tableHTML = `<table class="min-w-full bg-white"><thead class="bg-gray-50"><tr>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ลำดับ</th>
                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ยศ-ชื่อ-สกุล</th>
                ${is_admin ? '<th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">แผนก</th>' : ''}
            </tr></thead><tbody class="bg-white divide-y divide-gray-200">`;
            filteredAvailable.forEach((p, index) => {
                const fullName = `${escapeHTML(p.rank)} ${escapeHTML(p.first_name)} ${escapeHTML(p.last_name)}`;
                tableHTML += `<tr class="bg-green-50/50">
                    <td class="px-4 py-2">${index + 1}</td>
                    <td class="px-4 py-2">${fullName}</td>
                    ${is_admin ? `<td class="px-4 py-2">${escapeHTML(p.department)}</td>` : ''}
                </tr>`;
            });
            tableHTML += `</tbody></table>`;
            availableContainer.innerHTML = tableHTML;
        }
    }
}

// Main function to set up the status view
export function renderActiveStatuses(res) {
    fullStatusDataCache = res; // Cache the data
    const titleEl = document.getElementById('active-statuses-title');
    const filterContainer = document.getElementById('status-filter-container');

    if (!titleEl || !filterContainer) return;

    if (window.currentUser.role !== 'admin') {
        titleEl.textContent = `สถานะกำลังพล แผนก ${escapeHTML(window.currentUser.department)}`;
    } else {
        titleEl.textContent = `สถานะกำลังพล (ภาพรวม)`;
    }

    // Render filter buttons
    filterContainer.innerHTML = '';
    const filters = ['ทั้งหมด', 'ว่าง', ...Object.keys(STATUS_COLORS)];
    
    filters.forEach(filter => {
        const button = document.createElement('button');
        button.textContent = filter;
        button.dataset.filter = filter;
        button.className = 'status-filter-btn px-3 py-1 text-sm font-medium rounded-full border transition-colors bg-white text-gray-700 border-gray-300';
        
        button.addEventListener('click', () => {
            updateActiveStatusesView(filter);
        });

        filterContainer.appendChild(button);
    });

    // Render the initial view with 'ทั้งหมด' filter
    updateActiveStatusesView('ทั้งหมด');
}
