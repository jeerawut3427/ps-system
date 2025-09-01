// utils.js
// Contains helper and utility functions for data formatting and export.

// --- Helper Functions ---

function toThaiNumerals(n) {
    if (n === null || n === undefined) return '';
    const thaiDigits = ['๐', '๑', '๒', '๓', '๔', '๕', '๖', '๗', '๘', '๙'];
    return n.toString().replace(/[0-9]/g, d => thaiDigits[parseInt(d)]);
}

function getThaiHeaderDate(date) {
    const thaiMonths = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"];
    const d = new Date(date);
    const day = d.getDate();
    const month = thaiMonths[d.getMonth()];
    const year = d.getFullYear() + 543;
    return `${toThaiNumerals(day)} ${month} ${toThaiNumerals(year)}`;
}

export function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return str.toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// --- Arabic Numeral Formatters (for UI Display) ---

export function formatThaiDateArabic(isoDate) {
    if (!isoDate) return '';
    const date = new Date(isoDate);
    const thaiMonthsAbbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
    const year = date.getFullYear() + 543;
    const month = thaiMonthsAbbr[date.getMonth()];
    const day = date.getDate();
    return `${day} ${month}${String(year).slice(-2)}`;
}

export function formatThaiDateRangeArabic(startDateIso, endDateIso) {
    if (!startDateIso || !endDateIso) return 'N/A';
    
    const thaiMonthsAbbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
    const startDate = new Date(startDateIso);
    const endDate = new Date(endDateIso);

    if (startDate.getTime() === endDate.getTime()) {
        return formatThaiDateArabic(startDateIso);
    }

    const startDay = startDate.getDate();
    const startMonthAbbr = thaiMonthsAbbr[startDate.getMonth()];
    const startYearBE = startDate.getFullYear() + 543;

    const endDay = endDate.getDate();
    const endMonthAbbr = thaiMonthsAbbr[endDate.getMonth()];
    const endYearBE = endDate.getFullYear() + 543;

    if (startYearBE !== endYearBE) {
        return `${startDay} ${startMonthAbbr}${String(startYearBE).slice(-2)} - ${endDay} ${endMonthAbbr}${String(endYearBE).slice(-2)}`;
    }

    if (startDate.getMonth() !== endDate.getMonth()) {
        return `${startDay} ${startMonthAbbr} - ${endDay} ${endMonthAbbr}${String(endYearBE).slice(-2)}`;
    }

    return `${startDay} - ${endDay} ${startMonthAbbr}${String(endYearBE).slice(-2)}`;
}


// --- Thai Numeral Formatters (for Excel Export) ---

function formatThaiDateThai(isoDate) {
    if (!isoDate) return '';
    const date = new Date(isoDate);
    const thaiMonthsAbbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
    const year = date.getFullYear() + 543;
    const month = thaiMonthsAbbr[date.getMonth()];
    const day = date.getDate();
    return `${toThaiNumerals(day)} ${month}${toThaiNumerals(String(year).slice(-2))}`;
}

function formatThaiDateRangeThai(startDateIso, endDateIso) {
    if (!startDateIso || !endDateIso) return 'N/A';
    
    const thaiMonthsAbbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
    const startDate = new Date(startDateIso);
    const endDate = new Date(endDateIso);

    if (startDate.getTime() === endDate.getTime()) {
        return formatThaiDateThai(startDateIso);
    }

    const startDay = startDate.getDate();
    const startMonthAbbr = thaiMonthsAbbr[startDate.getMonth()];
    const startYearBE = startDate.getFullYear() + 543;

    const endDay = endDate.getDate();
    const endMonthAbbr = thaiMonthsAbbr[endDate.getMonth()];
    const endYearBE = endDate.getFullYear() + 543;

    if (startYearBE !== endYearBE) {
        return `${toThaiNumerals(startDay)} ${startMonthAbbr}${toThaiNumerals(String(startYearBE).slice(-2))} - ${toThaiNumerals(endDay)} ${endMonthAbbr}${toThaiNumerals(String(endYearBE).slice(-2))}`;
    }

    if (startDate.getMonth() !== endDate.getMonth()) {
        return `${toThaiNumerals(startDay)} ${startMonthAbbr} - ${toThaiNumerals(endDay)} ${endMonthAbbr}${toThaiNumerals(String(endYearBE).slice(-2))}`;
    }

    return `${toThaiNumerals(startDay)} - ${toThaiNumerals(endDay)} ${startMonthAbbr}${toThaiNumerals(String(endYearBE).slice(-2))}`;
}


export function exportSingleReportToExcel(reports, fileName, weekRangeText) {
    const dataForExport = [];
    let allItems = [];
    reports.forEach(report => {
        allItems = allItems.concat(report.items);
    });

    allItems.forEach((item, index) => {
        const nameParts = item.personnel_name.split(' ');
        const rank = nameParts.length > 0 ? nameParts[0] : '';
        const firstName = nameParts.length > 1 ? nameParts[1] : '';
        const lastName = nameParts.length > 2 ? nameParts.slice(2).join(' ') : '';
        
        const fullName = `${firstName}  ${lastName}`;
        const dateRange = formatThaiDateRangeThai(item.start_date, item.end_date);
        
        let combinedDetails = item.status;
        if (item.details) {
            combinedDetails += ` ${toThaiNumerals(item.details)}`; // Convert numbers in details to Thai numerals
        }
        combinedDetails += ` (${dateRange})`;

        dataForExport.push({
            'ลำดับ': toThaiNumerals(index + 1),
            'ชื่อ': fullName,
            'ยศ': rank,
            'สภาพการณ์หรือการเปลี่ยนแปลง': combinedDetails,
            'หมายเหตุ': ''
        });
    });

    let dateRangeString;
    if (weekRangeText) {
        dateRangeString = `ระหว่างวันที่ ${weekRangeText.replace(/[()]/g, '').trim()}`;
    } else {
        const allDates = reports.map(r => new Date(r.date));
        if (allDates.length > 0) {
            const minDate = new Date(Math.min.apply(null, allDates));
            const maxDate = new Date(Math.max.apply(null, allDates));
            if (minDate.getTime() === maxDate.getTime()) {
                dateRangeString = `ประจำวันที่ ${getThaiHeaderDate(minDate)}`;
            } else {
                dateRangeString = `ระหว่างวันที่ ${getThaiHeaderDate(minDate)} ถึง ${getThaiHeaderDate(maxDate)}`;
            }
        } else {
            dateRangeString = "ไม่ระบุช่วงวันที่";
        }
    }

    const wb = XLSX.utils.book_new();
    const ws_data = [
        ["บัญชีรายชื่อ น.สัญญาบัตรที่ไปราชการ, คุมงาน, ศึกษา, ลากิจ และลาพักผ่อน ประจำสัปดาห์ของ กวก.ชย.ทอ."],
        [dateRangeString],
        ["ลำดับ", "ชื่อ", "ยศ", "สภาพการณ์หรือการเปลี่ยนแปลง", "หมายเหตุ"]
    ];

    dataForExport.forEach(row => {
        ws_data.push([
            row['ลำดับ'],
            row['ชื่อ'],
            row['ยศ'],
            row['สภาพการณ์หรือการเปลี่ยนแปลง'],
            row['หมายเหตุ']
        ]);
    });

    const ws = XLSX.utils.aoa_to_sheet(ws_data);

    ws['!merges'] = [
        { s: { r: 0, c: 0 }, e: { r: 0, c: 4 } }, // A1-E1
        { s: { r: 1, c: 0 }, e: { r: 1, c: 4 } }  // A2-E2
    ];

    ws['!cols'] = [
        { wch: 10 }, // ลำดับ
        { wch: 40 }, // ชื่อ
        { wch: 20 }, // ยศ
        { wch: 60 }, // สภาพการณ์หรือการเปลี่ยนแปลง
        { wch: 20 }  // หมายเหตุ
    ];

    XLSX.utils.book_append_sheet(wb, ws, "รายงาน");
    XLSX.writeFile(wb, fileName || "รายงาน.xlsx");
}
