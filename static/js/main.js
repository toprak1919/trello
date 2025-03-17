/**
 * Trello Due Date Monitor - Main JavaScript
 * Global functionality shared across all pages
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Format dates on page
    formatDates();
    
    // Add dark/light mode toggle functionality
    setupThemeToggle();
    
    // Animated entrance for cards
    animateCards();
});

/**
 * Format all date elements on the page
 */
function formatDates() {
    // Format dates in a user-friendly way
    document.querySelectorAll('.format-date').forEach(element => {
        const dateStr = element.textContent.trim();
        if (dateStr && dateStr !== 'None' && dateStr !== 'Not set') {
            try {
                const date = new Date(dateStr);
                if (!isNaN(date)) {
                    // Format: "March 17, 2025 at 3:30 PM"
                    const options = { 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    };
                    element.textContent = date.toLocaleDateString(undefined, options);
                    
                    // Add relative time as title attribute (e.g., "2 days ago", "in 3 days")
                    const now = new Date();
                    const diffTime = date - now;
                    const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));
                    
                    let relativeTime = '';
                    if (diffDays === 0) {
                        relativeTime = 'Today';
                    } else if (diffDays === 1) {
                        relativeTime = 'Tomorrow';
                    } else if (diffDays === -1) {
                        relativeTime = 'Yesterday';
                    } else if (diffDays > 1) {
                        relativeTime = `In ${diffDays} days`;
                    } else {
                        relativeTime = `${Math.abs(diffDays)} days ago`;
                    }
                    
                    element.setAttribute('title', relativeTime);
                    element.setAttribute('data-bs-toggle', 'tooltip');
                }
            } catch (e) {
                console.error('Error formatting date:', e);
            }
        }
    });
}

/**
 * Set up theme toggle functionality
 */
function setupThemeToggle() {
    const themeToggleBtn = document.getElementById('themeToggle');
    if (!themeToggleBtn) return;
    
    // Check for saved theme preference or use preferred color scheme
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    // Set initial theme
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.body.classList.add('dark-theme');
        themeToggleBtn.innerHTML = '<i class="fas fa-sun"></i>';
    } else {
        themeToggleBtn.innerHTML = '<i class="fas fa-moon"></i>';
    }
    
    // Handle theme toggle
    themeToggleBtn.addEventListener('click', function() {
        if (document.body.classList.contains('dark-theme')) {
            document.body.classList.remove('dark-theme');
            localStorage.setItem('theme', 'light');
            themeToggleBtn.innerHTML = '<i class="fas fa-moon"></i>';
        } else {
            document.body.classList.add('dark-theme');
            localStorage.setItem('theme', 'dark');
            themeToggleBtn.innerHTML = '<i class="fas fa-sun"></i>';
        }
    });
}

/**
 * Animate cards entrance with a staggered effect
 */
function animateCards() {
    const cards = document.querySelectorAll('.card');
    
    if (cards.length === 0) return;
    
    // Add initial invisible class
    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    });
    
    // Staggered animation
    let delay = 100;
    cards.forEach(card => {
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, delay);
        delay += 100;
    });
}

/**
 * Format relative time (e.g., "2 hours ago")
 * @param {string} dateString - ISO date string
 * @return {string} Relative time
 */
function formatRelativeTime(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.round(diffMs / 1000);
    const diffMin = Math.round(diffSec / 60);
    const diffHour = Math.round(diffMin / 60);
    const diffDay = Math.round(diffHour / 24);
    
    if (diffSec < 60) {
        return diffSec + ' second' + (diffSec !== 1 ? 's' : '') + ' ago';
    } else if (diffMin < 60) {
        return diffMin + ' minute' + (diffMin !== 1 ? 's' : '') + ' ago';
    } else if (diffHour < 24) {
        return diffHour + ' hour' + (diffHour !== 1 ? 's' : '') + ' ago';
    } else if (diffDay < 30) {
        return diffDay + ' day' + (diffDay !== 1 ? 's' : '') + ' ago';
    } else {
        const diffMonth = Math.round(diffDay / 30);
        return diffMonth + ' month' + (diffMonth !== 1 ? 's' : '') + ' ago';
    }
}

/**
 * Show notification for new reminders
 * @param {string} message - Notification message
 */
function showNotification(message) {
    // Check if browser supports notifications
    if (!("Notification" in window)) {
        console.log("This browser does not support desktop notifications");
        return;
    }
    
    // Check if permission is already granted
    if (Notification.permission === "granted") {
        createNotification(message);
    }
    // Otherwise, request permission
    else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(function(permission) {
            if (permission === "granted") {
                createNotification(message);
            }
        });
    }
}

/**
 * Create and show a notification
 * @param {string} message - Notification message
 */
function createNotification(message) {
    const notification = new Notification("Trello Due Date Reminder", {
        body: message,
        icon: "/static/favicon.ico"
    });
    
    // Close the notification after 5 seconds
    setTimeout(() => {
        notification.close();
    }, 5000);
    
    // Handle notification click
    notification.onclick = function() {
        window.focus();
        this.close();
    };
} 