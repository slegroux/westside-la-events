// Toast Notification System
const Toast = {
    container: null,

    init() {
        // Get or create toast container
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            document.body.appendChild(this.container);
        }
    },

    show(message, type = 'info', title = null, duration = 4000) {
        if (!this.container) this.init();

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        // Icon based on type
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        const icon = icons[type] || icons.info;

        // Build toast content
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">
                ${title ? `<div class="toast-title">${title}</div>` : ''}
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" onclick="Toast.hide(this.parentElement)">×</button>
        `;

        // Add to container
        this.container.appendChild(toast);

        // Auto-hide after duration
        if (duration > 0) {
            setTimeout(() => this.hide(toast), duration);
        }

        return toast;
    },

    hide(toast) {
        if (!toast) return;

        // Add hiding class for animation
        toast.classList.add('hiding');

        // Remove from DOM after animation
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    },

    // Convenience methods
    success(message, title = 'Success') {
        return this.show(message, 'success', title);
    },

    error(message, title = 'Error') {
        return this.show(message, 'error', title);
    },

    warning(message, title = 'Warning') {
        return this.show(message, 'warning', title);
    },

    info(message, title = null) {
        return this.show(message, 'info', title);
    }
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', function() {
    Toast.init();
});

// Make Toast globally accessible
window.Toast = Toast;

// HTMX Integration - Show toasts for favorites actions
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Check if this is a favorite action by looking at the URL
    const xhr = event.detail.xhr;
    if (xhr && xhr.responseURL) {
        if (xhr.responseURL.includes('/favorites/add/')) {
            Toast.success('Event added to your favorites');
        } else if (xhr.responseURL.includes('/favorites/remove/')) {
            Toast.info('Event removed from favorites');
        }
    }
});

// Show error toast on HTMX errors
document.body.addEventListener('htmx:responseError', function(event) {
    const status = event.detail.xhr ? event.detail.xhr.status : 'Unknown';
    Toast.error(`Failed to load content (${status})`, 'Connection Error');
});

document.body.addEventListener('htmx:timeout', function(event) {
    Toast.error('The request took too long. Please try again.', 'Timeout');
});
