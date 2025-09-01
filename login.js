const API_URL = '/api';

const loginForm = document.getElementById('login-form');
const messageArea = document.getElementById('message-area');
const usernameInput = document.getElementById('login-username');

// --- START: Input Sanitization ---
// Add an event listener to the username input field.
usernameInput.addEventListener('input', () => {
    // This regular expression removes any character that is NOT a lowercase English letter (a-z).
    const sanitizedValue = usernameInput.value.toLowerCase().replace(/[^a-z]/g, '');
    // Update the input field's value with the sanitized version in real-time.
    usernameInput.value = sanitizedValue;
});
// --- END: Input Sanitization ---

function showMessage(message, isSuccess = true) {
    messageArea.textContent = message;
    messageArea.className = `mb-4 text-center p-3 rounded-lg ${isSuccess ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`;
}

function isPasswordComplex(password) {
    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;
    return passwordRegex.test(password);
}

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitButton = loginForm.querySelector('button[type="submit"]');
    const username = usernameInput.value; // Use the already sanitized value
    const password = loginForm.querySelector('#login-password').value;

    if (!isPasswordComplex(password)) {
        showMessage('รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร และประกอบด้วยตัวพิมพ์เล็ก, พิมพ์ใหญ่, และตัวเลข', false);
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'กำลังเข้าสู่ระบบ...';

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'login', payload: { username, password } })
        });
        
        const result = await response.json();

        if (response.ok && result.status === 'success' && result.user) {
            localStorage.setItem('currentUser', JSON.stringify(result.user));
            window.location.href = '/selection.html'; // เปลี่ยนเส้นทางไปที่หน้าเลือก
        } else {
            showMessage(result.message || 'เกิดข้อผิดพลาดในการล็อกอิน', false);
            submitButton.disabled = false;
            submitButton.textContent = 'เข้าสู่ระบบ';
        }
    } catch (error) {
        showMessage('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้', false);
        submitButton.disabled = false;
        submitButton.textContent = 'เข้าสู่ระบบ';
    }
});
