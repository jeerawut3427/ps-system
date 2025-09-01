// handlers.js
// Contains all event handler functions.

import { sendRequest } from './api.js';
import { showMessage, openPersonnelModal, openUserModal, renderArchivedReports, renderFilteredHistoryReports, showConfirmModal, showAlertModal } from './ui.js';
import { exportSingleReportToExcel, formatThaiDateArabic, formatThaiDateRangeArabic, escapeHTML } from './utils.js';

// All functions access global variables and DOM via the window object

export async function handlePersonnelFormSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const requiredFields = [
        { id: 'person-rank', name: 'ยศ - คำนำหน้า' },
        { id: 'person-first-name', name: 'ชื่อ' },
        { id: 'person-last-name', name: 'นามสกุล' },
        { id: 'person-position', name: 'ตำแหน่ง' },
        { id: 'person-department', name: 'แผนก' }
    ];

    const missingFields = requiredFields.filter(field => !form.querySelector(`#${field.id}`).value);

    if (missingFields.length > 0) {
        const missingFieldNames = missingFields.map(field => field.name).join('<br>- ');
        showAlertModal('ข้อมูลไม่ครบถ้วน', `กรุณากรอกข้อมูลต่อไปนี้:<br>- ${missingFieldNames}`);
        return;
    }

    const personId = form.querySelector('#person-id').value;
    const data = {
        id: personId,
        rank: form.querySelector('#person-rank').value,
        first_name: form.querySelector('#person-first-name').value,
        last_name: form.querySelector('#person-last-name').value,
        position: form.querySelector('#person-position').value,
        specialty: form.querySelector('#person-specialty').value,
        department: form.querySelector('#person-department').value,
        personnel_type: form.querySelector('#person-type').value,
    };
    const action = personId ? 'update_personnel' : 'add_personnel';
    try {
        const response = await sendRequest(action, { data });
        if (response.status === 'success') {
            window.personnelModal.classList.remove('active');
            window.loadDataForPane('pane-personnel');
        }
        showMessage(response.message, response.status === 'success');
    } catch (error) {
        showMessage(error.message, false);
    }
}

export async function handlePersonnelListClick(e) {
    const target = e.target;
    const personId = target.dataset.id;
    if (!personId) return;

    if (target.classList.contains('delete-person-btn')) {
        showConfirmModal('ยืนยันการลบข้อมูล', 'คุณแน่ใจหรือไม่ว่าต้องการลบข้อมูลกำลังพลนี้?', async () => {
            try {
                const response = await sendRequest('delete_personnel', { id: personId });
                if (response.status === 'success') window.loadDataForPane('pane-personnel');
                showMessage(response.message, response.status === 'success');
            } catch(error) {
                showMessage(error.message, false);
            }
        });
    } else if (target.classList.contains('edit-person-btn')) {
        try {
            const res = await sendRequest('get_personnel_details', { id: personId });
            if (res.status === 'success' && res.personnel) {
                openPersonnelModal(res.personnel);
            } else {
                showMessage(res.message || 'ไม่พบข้อมูลกำลังพลที่ต้องการแก้ไข', false);
            }
        } catch(error) {
            showMessage(error.message, false);
        }
    }
}

export async function handleUserFormSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const isNewUser = !form.querySelector('#user-username').readOnly;

    const requiredFields = [
        { id: 'user-username', name: 'Username' },
        { id: 'user-rank', name: 'ยศ-คำนำหน้า' },
        { id: 'user-first-name', name: 'ชื่อ' },
        { id: 'user-last-name', name: 'นามสกุล' },
        { id: 'user-position', name: 'ตำแหน่ง' },
        { id: 'user-department', name: 'แผนก' }
    ];

    if (isNewUser) {
        requiredFields.push({ id: 'user-password', name: 'Password' });
    }

    const missingFields = requiredFields.filter(field => !form.querySelector(`#${field.id}`).value);

    if (missingFields.length > 0) {
        const missingFieldNames = missingFields.map(field => field.name).join('<br>- ');
        showAlertModal('ข้อมูลไม่ครบถ้วน', `กรุณากรอกข้อมูลต่อไปนี้:<br>- ${missingFieldNames}`);
        return;
    }

    const username = form.querySelector('#user-username').value;
    const password = form.querySelector('#user-password').value;
    const data = {
        username: username,
        password: password,
        rank: form.querySelector('#user-rank').value,
        first_name: form.querySelector('#user-first-name').value,
        last_name: form.querySelector('#user-last-name').value,
        position: form.querySelector('#user-position').value,
        department: form.querySelector('#user-department').value,
        role: form.querySelector('#user-role').value,
    };
    if (!password) delete data.password;
    const action = isNewUser ? 'add_user' : 'update_user';
    
    try {
        const response = await sendRequest(action, { data });
        if (response.status === 'success') {
            window.userModal.classList.remove('active');
            window.loadDataForPane('pane-admin');
        }
        showMessage(response.message, response.status === 'success');
    } catch(error) {
        showMessage(error.message, false);
    }
}

export async function handleUserListClick(e) {
    const target = e.target;
    const username = target.dataset.username;
    if (!username) return;

    if (target.classList.contains('delete-user-btn')) {
        showConfirmModal('ยืนยันการลบผู้ใช้', `คุณแน่ใจหรือไม่ว่าต้องการลบผู้ใช้ '${username}'?`, async () => {
            try {
                const response = await sendRequest('delete_user', { username: username });
                if (response.status === 'success') window.loadDataForPane('pane-admin');
                showMessage(response.message, response.status === 'success');
            } catch(error) {
                showMessage(error.message, false);
            }
        });
    } else if (target.classList.contains('edit-user-btn')) {
        try {
            const res = await sendRequest('list_users', { page: 1, searchTerm: '' });
            if (res.status === 'success') {
                const userToEdit = res.users.find(u => u.username === username);
                if (userToEdit) openUserModal(userToEdit);
                else showMessage('ไม่พบข้อมูลผู้ใช้ที่ต้องการแก้ไข', false);
            }
        } catch(error) {
            showMessage(error.message, false);
        }
    }
}

export function handleExcelImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, { type: 'array' });
            const firstSheetName = workbook.SheetNames[0];
            const worksheet = workbook.Sheets[firstSheetName];
            const json = XLSX.utils.sheet_to_json(worksheet);
            const formattedData = json.map(row => ({
                'ยศ-คำนำหน้า': row['ยศ-คำนำหน้า'], 
                'ชื่อ': row['ชื่อ'], 
                'นามสกุล': row['นามสกุล'],
                'ตำแหน่ง': row['ตำแหน่ง'], 
                'เหล่า': row['เหล่า'], 
                'แผนก': row['แผนก'],
                'ประเภท': row['ประเภท']
            }));
            const response = await sendRequest('import_personnel', { personnel: formattedData });
            if (response.status === 'success') {
                window.loadDataForPane('pane-personnel');
            }
            showMessage(response.message, response.status === 'success');
        } catch (error) {
            console.error("Error processing Excel file:", error);
            showMessage("เกิดข้อผิดพลาดในการประมวลผลไฟล์ Excel", false);
        } finally {
            window.excelImportInput.value = '';
        }
    };
    reader.readAsArrayBuffer(file);
}

export function handleReviewStatus() {
    const rows = window.statusSubmissionListArea.querySelectorAll('tr');
    const reviewItems = [];
    let hasError = false;

    if (rows.length === 0) {
        showMessage('ไม่พบข้อมูลกำลังพลที่จะส่ง', false);
        return;
    }

    rows.forEach(row => {
        const statusSelect = row.querySelector('.status-select');
        if (statusSelect && statusSelect.value !== 'ไม่มี') {
            const startDate = row.querySelector('.start-date-input').value;
            const endDate = row.querySelector('.end-date-input').value;
            if (!startDate || !endDate) {
                showAlertModal('ข้อมูลไม่ครบถ้วน', 'กรุณากรอกวันที่เริ่มต้นและสิ้นสุดสำหรับรายการที่เลือก');
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
        window.reviewListArea.innerHTML = `<tr><td colspan="4" class="text-center py-4 text-gray-500">ยืนยันการส่งยอด: กำลังพลมาปฏิบัติงานครบถ้วน</td></tr>`;
    } else {
        window.reviewListArea.innerHTML = reviewItems.map(item => {
            const dateRange = formatThaiDateRangeArabic(item.start_date, item.end_date);
            return `<tr>
                        <td class="border-t px-4 py-2">${escapeHTML(item.personnel_name)}</td>
                        <td class="border-t px-4 py-2">${escapeHTML(item.status)}</td>
                        <td class="border-t px-4 py-2">${escapeHTML(item.details) || '-'}</td>
                        <td class="border-t px-4 py-2">${dateRange}</td>
                    </tr>`;
        }).join('');
    }

    window.submissionFormSection.classList.add('hidden');
    window.reviewReportSection.classList.remove('hidden');
}

export async function handleSubmitStatusReport() {
    const confirmBtn = document.getElementById('confirm-submit-btn');
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'กำลังส่ง...';
    }

    const rows = window.statusSubmissionListArea.querySelectorAll('tr');
    const reportItems = [];
    
    rows.forEach(row => {
        const statusSelect = row.querySelector('.status-select');
        if (statusSelect && statusSelect.value !== 'ไม่มี') {
            reportItems.push({
                personnel_id: row.dataset.personnelId, 
                personnel_name: row.dataset.personnelName,
                status: statusSelect.value, 
                details: row.querySelector('.details-input').value,
                start_date: row.querySelector('.start-date-input').value,
                end_date: row.querySelector('.end-date-input').value
            });
        }
    });

    let reportDepartment = window.currentUser.department;
    if (window.currentUser.role === 'admin') {
        const deptSelector = document.getElementById('admin-dept-selector');
        if (deptSelector) {
            reportDepartment = deptSelector.value;
        }
    }

    const report = {
        items: reportItems,
        department: reportDepartment
    };

    try {
        const response = await sendRequest('submit_status_report', { report });
        showMessage(response.message, response.status === 'success');
        if (response.status === 'success') {
            reviewReportSection.classList.add('hidden');
            if (window.currentUser.role === 'admin') {
                window.switchTab('tab-dashboard');
            } else {
                window.loadDataForPane('pane-submit-status');
            }
        }
    } catch(error) {
        showMessage(error.message, false);
    } finally {
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'ยืนยันและส่งยอด';
        }
    }
}

export async function handleExportAndArchive() {
    const weekRangeText = document.getElementById('report-week-range')?.textContent || '';
    window.archiveConfirmModal.classList.remove('active');
    if (!window.currentWeeklyReports || window.currentWeeklyReports.length === 0) {
        showMessage('ไม่มีข้อมูลรายงานที่จะส่งออก', false);
        return;
    }
    exportSingleReportToExcel(window.currentWeeklyReports, `รายงานกำลังพล-${new Date().toISOString().split('T')[0]}.xlsx`, weekRangeText);
    try {
        const response = await sendRequest('archive_reports', { reports: window.currentWeeklyReports });
        showMessage(response.message, response.status === 'success');
        if (response.status === 'success') {
            window.loadDataForPane('pane-report');
        }
    } catch(error) {
        showMessage(error.message, false);
    }
}

export function handleShowArchive() {
    const year = window.archiveYearSelect.value;
    const month = window.archiveMonthSelect.value;
    if (!year || !month) {
        showAlertModal('ข้อมูลไม่ครบถ้วน', 'กรุณาเลือกปีและเดือน');
        return;
    }
    const reportsForMonth = window.allArchivedReports[year] ? window.allArchivedReports[year][month] : [];
    renderArchivedReports(reportsForMonth);
}

export function handleArchiveDownloadClick(e) {
    if (e.target.classList.contains('download-daily-archive-btn')) {
        const date = e.target.dataset.date;
        const year = window.archiveYearSelect.value;
        const month = window.archiveMonthSelect.value;
        if (!year || !month || !date) {
            showAlertModal('ข้อมูลไม่ครบถ้วน', 'กรุณาเลือกปีและเดือนก่อนดาวน์โหลด');
            return;
        }

        const reportsForMonth = window.allArchivedReports[year] ? window.allArchivedReports[year][month] : [];
        
        if (!reportsForMonth || !Array.isArray(reportsForMonth)) {
            showMessage('เกิดข้อผิดพลาด: ไม่พบข้อมูลสำหรับเดือนที่เลือก', false);
            return;
        }

        const reportsToDownload = reportsForMonth.filter(r => r.date === date);
        
        if (reportsToDownload.length > 0) {
            exportSingleReportToExcel(reportsToDownload, `รายงานย้อนหลัง-${date}.xlsx`);
        } else {
            showMessage('ไม่พบข้อมูลรายงานที่จะดาวน์โหลดสำหรับวันนี้', false);
        }
    }
}

export async function handleHistoryEditClick(e) {
    const target = e.target;
    if (!target.classList.contains('edit-history-btn')) return;

    const reportId = target.dataset.id;
    if (!reportId) return;

    try {
        const res = await sendRequest('get_report_for_editing', { id: reportId });
        if (res.status === 'success' && res.report) {
            window.editingReportData = res.report;
            window.switchTab('tab-submit-status');
        } else {
            showMessage(res.message || 'ไม่สามารถดึงข้อมูลมาแก้ไขได้', false);
        }
    } catch (error) {
        showMessage(error.message, false);
    }
}

export function handleShowHistory() {
    const year = window.historyYearSelect.value;
    const month = window.historyMonthSelect.value;
    if (!year || !month) {
        showAlertModal('ข้อมูลไม่ครบถ้วน', 'กรุณาเลือกปีและเดือน');
        return;
    }
    const reportsForMonth = window.allHistoryData[year] ? window.allHistoryData[year][month] : [];
    renderFilteredHistoryReports(reportsForMonth);
}

export async function handleWeeklyReportEditClick(e) {
    const target = e.target;
    if (!target.classList.contains('edit-weekly-report-btn')) return;

    const reportId = target.dataset.id;
    if (!reportId) return;

    try {
        const res = await sendRequest('get_report_for_editing', { id: reportId });
        if (res.status === 'success' && res.report) {
            window.editingReportData = res.report;
            window.switchTab('tab-submit-status');
        } else {
            showMessage(res.message || 'ไม่สามารถดึงข้อมูลมาแก้ไขได้', false);
        }
    } catch (error) {
        showMessage(error.message, false);
    }
}

