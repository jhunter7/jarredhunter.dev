/* ============================================
   Jarred Hunter — jarredhunter.dev
   Direction 1 · theme toggle, smooth scroll, reveal
   ============================================ */

(function () {
  'use strict';

  var root = document.documentElement;
  var toggle = document.getElementById('theme-toggle');
  var STORAGE_KEY = 'jh-theme';

  /* Default to OS preference; remember explicit user choice after that */
  function getInitialTheme() {
    var saved = null;
    try { saved = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    if (saved === 'light' || saved === 'dark') return saved;
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light';
    }
    return 'dark';
  }

  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (e) {}
  }

  applyTheme(getInitialTheme());

  /* If the user hasn't picked manually, keep following OS changes live */
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function (e) {
      var saved = null;
      try { saved = localStorage.getItem(STORAGE_KEY + '-manual'); } catch (err) {}
      if (!saved) root.setAttribute('data-theme', e.matches ? 'light' : 'dark');
    });
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try { localStorage.setItem(STORAGE_KEY + '-manual', '1'); } catch (e) {}
    });
  }

  /* Smooth scroll for in-page anchors */
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var id = this.getAttribute('href');
      if (id === '#' || id.length < 2) return;
      var target = document.querySelector(id);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  /* Scroll-triggered reveal */
  var revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach(function (el) { observer.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('visible'); });
  }

  /* Blog: copy button on fenced code blocks */
  function initBlogCopyButtons() {
    document.querySelectorAll('.blog-content pre').forEach(function (pre) {
      if (pre.closest('.code-block-wrap')) return;

      var wrap = document.createElement('div');
      wrap.className = 'code-block-wrap';
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'copy-code-btn';
      btn.setAttribute('aria-label', 'Copy code to clipboard');
      btn.textContent = 'copy';
      wrap.insertBefore(btn, pre);

      btn.addEventListener('click', function () {
        var code = pre.querySelector('code');
        var text = code ? code.innerText : pre.innerText;

        function showCopied() {
          btn.textContent = 'copied';
          btn.classList.add('copied');
          setTimeout(function () {
            btn.textContent = 'copy';
            btn.classList.remove('copied');
          }, 2000);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(showCopied).catch(function () {
            fallbackCopy(text);
            showCopied();
          });
        } else {
          fallbackCopy(text);
          showCopied();
        }
      });
    });
  }

  function fallbackCopy(text) {
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.left = '-9999px';
    document.body.appendChild(area);
    area.select();
    try { document.execCommand('copy'); } catch (e) { /* ignore */ }
    document.body.removeChild(area);
  }

  initBlogCopyButtons();

  /* Blog: click terminal screenshot to view full size */
  document.querySelectorAll('.terminal-shot').forEach(function (img) {
    var src = img.getAttribute('src');
    if (!src) return;
    var link = document.createElement('a');
    link.href = src;
    link.target = '_blank';
    link.rel = 'noopener';
    link.className = 'terminal-shot-link';
    link.setAttribute('aria-label', 'Open screenshot full size');
    img.parentNode.insertBefore(link, img);
    link.appendChild(img);
  });
})();
