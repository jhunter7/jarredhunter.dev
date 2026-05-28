const root = document.documentElement;
const themeToggle = document.getElementById('theme-toggle');
const THEME_KEY = 'site-theme';

function setTheme(theme) {
    const isDark = theme === 'dark';
    root.setAttribute('data-theme', isDark ? 'dark' : 'light');

    if (themeToggle) {
        themeToggle.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
        themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
        themeToggle.setAttribute('title', isDark ? 'Switch to light mode' : 'Switch to dark mode');
    }
}

const savedTheme = localStorage.getItem(THEME_KEY) || 'light';
setTheme(savedTheme);

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const nextTheme = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        localStorage.setItem(THEME_KEY, nextTheme);
        setTheme(nextTheme);
    });
}

// Smooth scrolling for in-page navigation with sticky-nav offset.
document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (!target) {
            return;
        }

        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
});