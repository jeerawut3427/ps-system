// api.js
// Handles all communication with the backend server.

const API_URL = '/api';

export async function sendRequest(action, payload = {}) {
    // No need to check for sessionToken here, the HttpOnly cookie is sent automatically by the browser.
    
    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            cache: 'no-cache',
            headers: {
                'Content-Type': 'application/json',
                // Authorization header is no longer needed as we use HttpOnly cookies.
            },
            body: JSON.stringify({ action, payload })
        });

        if (response.status === 401) {
            // Unauthorized, clear local data and redirect to login page.
            localStorage.removeItem('currentUser');
            window.location.href = '/login.html';
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
             // Try to parse the error message from the server's JSON response
             const errorResult = await response.json();
             throw new Error(errorResult.message || `Network response was not ok. Status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("API request failed:", error);
        // Throw the specific error message from the server if available, otherwise a generic one.
        throw new Error(error.message || 'การเชื่อมต่อกับเซิร์ฟเวอร์ล้มเหลว');
    }
}
