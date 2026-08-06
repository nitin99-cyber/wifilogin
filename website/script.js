document.addEventListener('DOMContentLoaded', () => {
  // 1. Header Scroll Shadow
  const header = document.querySelector('.header');
  function onScroll() {
    if (header) {
      header.classList.toggle('header--scrolled', window.scrollY > 10);
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // 2. Mobile Nav Toggle
  const navToggle = document.querySelector('.nav__toggle');
  const navLinks = document.querySelector('.nav__links');
  
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      navLinks.classList.toggle('nav__links--open');
      const isOpen = navLinks.classList.contains('nav__links--open');
      navToggle.setAttribute('aria-expanded', isOpen);
    });

    // Close nav when a nav link is clicked
    const links = navLinks.querySelectorAll('.nav__link');
    links.forEach(link => {
      link.addEventListener('click', () => {
        navLinks.classList.remove('nav__links--open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });

    // Close nav when clicking outside
    document.addEventListener('click', (e) => {
      if (!navLinks.contains(e.target) && !navToggle.contains(e.target) && navLinks.classList.contains('nav__links--open')) {
        navLinks.classList.remove('nav__links--open');
        navToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // 3. FAQ Accordion
  const faqQuestions = document.querySelectorAll('.faq__question');
  faqQuestions.forEach(question => {
    question.addEventListener('click', () => {
      const parent = question.closest('.faq__item');
      const answer = parent.querySelector('.faq__answer');
      const isOpen = parent.classList.contains('faq__item--open');

      // Close all first
      document.querySelectorAll('.faq__item--open').forEach(item => {
        item.classList.remove('faq__item--open');
        const ans = item.querySelector('.faq__answer');
        if (ans) ans.style.maxHeight = null;
        const q = item.querySelector('.faq__question');
        if (q) q.setAttribute('aria-expanded', 'false');
      });

      if (!isOpen) {
        parent.classList.add('faq__item--open');
        if (answer) answer.style.maxHeight = answer.scrollHeight + 'px';
        question.setAttribute('aria-expanded', 'true');
      }
    });
  });

  // 4. Screenshot Carousel
  const track = document.querySelector('.carousel__track');
  const slides = document.querySelectorAll('.carousel__slide');
  const prevBtn = document.querySelector('.carousel__prev');
  const nextBtn = document.querySelector('.carousel__next');
  const dots = document.querySelectorAll('.carousel__dot');
  const caption = document.getElementById('carousel-caption');
  const captions = ['Setup Window', 'About Window', 'Installer', 'Running App'];
  let currentSlide = 0;
  
  if (track && slides.length > 0) {
    function goToSlide(index) {
      if (index < 0) index = slides.length - 1;
      if (index >= slides.length) index = 0;
      currentSlide = index;
      track.style.transform = `translateX(-${currentSlide * 100}%)`;
      // Update dots
      dots.forEach((dot, i) => {
        dot.classList.toggle('carousel__dot--active', i === currentSlide);
      });
      // Update caption
      if (caption && captions[currentSlide]) {
        caption.textContent = captions[currentSlide];
      }
    }

    if (prevBtn) prevBtn.addEventListener('click', () => goToSlide(currentSlide - 1));
    if (nextBtn) nextBtn.addEventListener('click', () => goToSlide(currentSlide + 1));
    
    dots.forEach((dot, i) => {
      dot.addEventListener('click', () => goToSlide(i));
    });

    // Auto-rotate every 5 seconds
    let autoRotate = setInterval(() => goToSlide(currentSlide + 1), 5000);
    // Pause on hover
    const carousel = document.querySelector('.carousel');
    if (carousel) {
      carousel.addEventListener('mouseenter', () => clearInterval(autoRotate));
      carousel.addEventListener('mouseleave', () => {
        autoRotate = setInterval(() => goToSlide(currentSlide + 1), 5000);
      });
      
      // 9. Touch/Swipe support for carousel
      let touchStartX = 0;
      let touchEndX = 0;

      carousel.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
      }, { passive: true });
      
      carousel.addEventListener('touchend', (e) => {
        touchEndX = e.changedTouches[0].screenX;
        const diff = touchStartX - touchEndX;
        if (Math.abs(diff) > 50) {
          if (diff > 0) goToSlide(currentSlide + 1);
          else goToSlide(currentSlide - 1);
        }
      }, { passive: true });
    }
  }

  // 5. Scroll-Reveal Animations
  const revealElements = document.querySelectorAll('.reveal');
  if (revealElements.length > 0) {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('reveal--visible');
          // Stagger children if they have .reveal-child class
          const children = entry.target.querySelectorAll('.reveal-child');
          children.forEach((child, i) => {
            child.style.transitionDelay = `${i * 0.1}s`;
            child.classList.add('reveal-child--visible');
          });
          // Unobserve if we only want it to animate once
          // revealObserver.unobserve(entry.target); 
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(el => revealObserver.observe(el));
  }

  // 6. Active Nav Link on Scroll
  const sections = document.querySelectorAll('section[id]');
  const navItems = document.querySelectorAll('.nav__link');
  
  if (sections.length > 0 && navItems.length > 0) {
    function highlightNav() {
      let scrollY = window.scrollY;
      
      sections.forEach(current => {
        const sectionHeight = current.offsetHeight;
        const sectionTop = current.offsetTop - 100; // offset for header
        const sectionId = current.getAttribute('id');
        
        if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
          navItems.forEach(item => {
            item.classList.remove('nav__link--active');
            if (item.getAttribute('href') === `#${sectionId}`) {
              item.classList.add('nav__link--active');
            }
          });
        }
      });
    }
    window.addEventListener('scroll', highlightNav, { passive: true });
    highlightNav();
  }

  // 8. Download/GitHub click tracking (lightweight, no GA)
  const trackLinks = document.querySelectorAll('[data-track]');
  trackLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      const eventName = link.getAttribute('data-track');
      console.log(`Tracked click: ${eventName}`);
    });
  });
});
